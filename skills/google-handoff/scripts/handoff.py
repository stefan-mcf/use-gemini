"""Prepare and inspect local Antigravity handoffs. Never dispatches a model request."""

import argparse
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


JOBS = ".agent-handoffs"
ID = re.compile(r"[a-f0-9]{12}")


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def workspace_file(root, name):
    parts = name.split("/")
    if (not name.strip() or "\\" in name or "\x00" in name or PureWindowsPath(name).drive
            or any(part in ("", ".", "..") for part in parts) or parts[0] == JOBS):
        raise ValueError(f"Expected a workspace-relative file path: {name!r}")
    path = root.joinpath(*parts)
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or resolved.is_relative_to(root / JOBS):
        raise ValueError(f"File path resolves outside the work area: {name!r}")
    if (path.exists() or path.is_symlink()) and not path.is_file():
        raise ValueError(f"Expected a regular file: {name!r}")
    return path


def baseline(root, paths):
    files = {}
    for name in paths:
        path = workspace_file(root, name)
        files[name] = digest(path) if path.is_file() else None
    data = {"workspace": str(root), "files_sha256": files, "git": None}
    if shutil.which("git") is None:
        return data

    def git(*args, check=True):
        return subprocess.run(["git", "--no-optional-locks", "-C", str(root), *args],
                              capture_output=True, check=check, encoding="utf-8", errors="replace")

    top = git("rev-parse", "--show-toplevel", check=False)
    if top.returncode == 0:
        head = git("rev-parse", "--verify", "HEAD", check=False)
        data["git"] = {
            "root": top.stdout.strip(),
            "head": head.stdout.strip() or None,
            "branch": git("branch", "--show-current").stdout.strip() or None,
            "starting_status": git("status", "--porcelain=v1", "--untracked-files=all",
                                   "--", ".", f":(exclude){JOBS}").stdout.splitlines(),
        }
    return data


def prepare(root, jobs, paths, brief, previous):
    if not brief:
        raise ValueError("Supply the task brief on stdin.")
    if previous:
        if not ID.fullmatch(previous) or "result_sha256" not in inspect_job(root, jobs / previous):
            raise ValueError("The previous handoff needs a valid return in this workspace.")
    job = uuid.uuid4().hex[:12]
    relative = f"{JOBS}/{job}"
    before = baseline(root, paths)
    before["job"] = job
    before["title"] = brief.splitlines()[0].lstrip("# ").strip()
    prior_note = ""
    if previous:
        before["previous_job"] = previous
        prior_note = f"Previous handoff: `{previous}`\n\n"
    prompt = f"Read {relative}/REQUEST.md in this workspace. Carry out the brief and return the result as specified."
    request = f"""# Antigravity handoff {job}

Workspace: {root}

{prior_note}{brief}

## Return to Codex

Work in the recorded workspace. Preserve existing edits and follow its project instructions.
If this job already has a RESULT.json, read it and stop to avoid repeating work.
Before starting the task, claim it by creating the STARTED directory beside this request
with a single mkdir that fails if it already exists. If it exists, resume only when the
user asks you to resume this job and confirms the previous session is inactive.
Finish the checks, then publish your result beside this request. Write RESULT.tmp first
and rename it to RESULT.json when complete. Use the following JSON shape.

```json
{{"job":"{job}","outcome":"completed","summary":"Describe what happened.","files":[],"checks":[]}}
```

Use completed if the requested work and required checks succeeded, or blocked for
partial work or an unmet requirement. Describe the blocker in the summary. In files
list changed workspace-relative paths using forward slashes. Omit the handoff files.
In checks list the actual checks and outcomes.
Use empty arrays when applicable. Codex independently reviews the returned work.
"""
    jobs.mkdir(exist_ok=True, mode=0o700)
    try:
        with (jobs / ".gitignore").open("x", encoding="utf-8") as ignore:
            ignore.write("# Handoff requests, results, and reviews are workspace-local.\n*\n")
    except FileExistsError:
        pass
    target = jobs / job
    with tempfile.TemporaryDirectory(dir=jobs, prefix=".preparing-") as temp:
        staged = Path(temp) / job
        staged.mkdir(mode=0o700)
        (staged / "REQUEST.md").write_text(request, encoding="utf-8")
        (staged / "baseline.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
        staged.rename(target)
    return {"job": job, "workspace": str(root), "native_prompt": f"/codex-handoff {job}",
            "prompt": prompt}


def inspect_job(root, folder):
    info = {"job": folder.name, "state": "awaiting_return"}
    try:
        if not ID.fullmatch(folder.name) or folder.is_symlink() or not folder.is_dir():
            raise ValueError("Unknown job in this workspace.")
        baseline_file = folder / "baseline.json"
        if baseline_file.is_symlink() or not baseline_file.is_file():
            raise ValueError("Expected a regular baseline file.")
        before = json.loads(baseline_file.read_text(encoding="utf-8"))
        if not isinstance(before, dict) or before.get("workspace") != str(root) or before.get("job") != folder.name:
            raise ValueError("The handoff belongs to a different workspace or job.")
        if not isinstance(before.get("title"), str):
            raise ValueError("Missing job title.")
        info["title"] = before["title"]
        if "previous_job" in before:
            info["previous_job"] = before["previous_job"]
    except (ValueError, OSError) as error:
        return dict(info, state="invalid_job", reason=str(error))

    result = folder / "RESULT.json"
    if not result.exists() and not result.is_symlink():
        claim = folder / "STARTED"
        if claim.is_dir() and not claim.is_symlink():
            info["state"] = "claimed"
        return info
    try:
        if result.is_symlink() or not result.is_file():
            raise ValueError("Expected a regular result file.")
        raw = result.read_bytes()
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get("job") != folder.name:
            raise ValueError("Result job ID mismatch.")
        if value.get("outcome") not in ("completed", "blocked"):
            raise ValueError("Expected completed or blocked.")
        if not isinstance(value.get("summary"), str) or not value["summary"].strip():
            raise ValueError("Missing result summary.")
        for field in ("files", "checks"):
            items = value.get(field)
            if not isinstance(items, list) or not all(isinstance(i, str) and i.strip() for i in items):
                raise ValueError(f"Expected {field} to be a list of strings.")
        for name in value["files"]:
            workspace_file(root, name)
        info.update(state="ready_for_review" if value["outcome"] == "completed" else "blocked",
                    result=value, result_sha256=hashlib.sha256(raw).hexdigest())
    except (ValueError, OSError, RuntimeError) as error:
        return dict(info, state="invalid_return", reason=str(error))

    review = folder / "REVIEW.md"
    if review.exists() or review.is_symlink():
        info["review"] = "unmatched_review"
        try:
            if review.is_symlink() or not review.is_file():
                return info
            lines = review.read_text(encoding="utf-8").splitlines()
        except (ValueError, OSError):
            return info
        verdict_lines = [line for line in lines if line.startswith("Verdict:")]
        digest_lines = [line for line in lines if line.startswith("Result SHA-256:")]
        verdicts = {"Verdict: " + v: v for v in ("accepted", "needs_changes", "blocked")}
        verdict = verdicts.get(verdict_lines[0]) if len(verdict_lines) == 1 else None
        if (verdict and digest_lines == [f"Result SHA-256: {info['result_sha256']}"]
                and not (verdict == "accepted" and value["outcome"] == "blocked")):
            info.pop("review")
            info.update(state="review_recorded", verdict=verdict)
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="action", required=True)
    for name in ("prepare", "status", "wait"):
        mode = modes.add_parser(name)
        mode.add_argument("--workspace", required=True, type=Path)
        if name == "prepare":
            mode.add_argument("--track", action="append", default=[], metavar="FILE")
            mode.add_argument("--previous", metavar="JOB")
        else:
            mode.add_argument("--job", required=name == "wait")
    args = parser.parse_args()
    root = args.workspace.resolve(strict=True)
    jobs = root / JOBS
    if not root.is_dir() or jobs.is_symlink() or (jobs.exists() and not jobs.is_dir()):
        raise ValueError("Expected a workspace directory and a local handoff folder.")
    if args.action == "prepare":
        brief = sys.stdin.buffer.read().decode("utf-8-sig").strip()
        return prepare(root, jobs, args.track, brief, args.previous)
    if args.job is None:
        return [inspect_job(root, d) for d in sorted(jobs.glob("*")) if ID.fullmatch(d.name)]
    if not ID.fullmatch(args.job):
        raise ValueError("Invalid handoff ID.")
    deadline = time.monotonic() + (30 if args.action == "wait" else 0)
    while True:
        info = inspect_job(root, jobs / args.job)
        if info["state"] not in ("awaiting_return", "claimed") or time.monotonic() >= deadline:
            return info
        time.sleep(1)


if __name__ == "__main__":
    try:
        print(json.dumps(main(), indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
