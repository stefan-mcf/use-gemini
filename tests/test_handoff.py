import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / "skills/google-handoff/scripts/handoff.py"


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="handoff workspace ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.workspace = self.root / "workspace with spaces"
        self.workspace.mkdir()

    def run_helper(self, action, *options, brief=None, workspace=None, env=None):
        return subprocess.run(
            [
                sys.executable,
                str(HELPER),
                action,
                "--workspace",
                str(workspace or self.workspace),
                *options,
            ],
            input=brief,
            capture_output=True,
            check=False,
            encoding="utf-8",
            timeout=10,
            env=env,
        )

    def read_json(self, action, *options, **kwargs):
        process = self.run_helper(action, *options, **kwargs)
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def prepare(self, *options, **kwargs):
        return self.read_json("prepare", *options, brief="# Review the proposed change ↔", **kwargs)

    def job_path(self, job):
        return self.workspace / ".agent-handoffs" / job

    def return_result(self, job, *, files=(), outcome="completed", summary="Reviewed."):
        folder = self.job_path(job)
        result = {
            "job": job,
            "outcome": outcome,
            "summary": summary,
            "files": list(files),
            "checks": ["Compared the proposal with the requirements."],
        }
        raw = (json.dumps(result) + "\n").encode("utf-8")
        staged = folder / "RESULT.tmp"
        staged.write_bytes(raw)
        staged.replace(folder / "RESULT.json")
        return hashlib.sha256(raw).hexdigest()

    def test_prepare_status_and_wait_follow_the_manual_lifecycle(self):
        env = dict(os.environ, PATH=str(self.root), HOME=str(self.root), USERPROFILE=str(self.root))
        prepared = self.prepare(env=env)
        job = prepared["job"]
        folder = self.job_path(job)
        self.assertEqual(prepared["workspace"], str(self.workspace))
        self.assertEqual(prepared["native_prompt"], f"/codex-handoff {job}")
        self.assertIn(f".agent-handoffs/{job}/REQUEST.md", prepared["prompt"])
        self.assertNotIn("launcher", prepared)
        self.assertNotIn("terminal_command", prepared)
        self.assertEqual({path.name for path in folder.iterdir()}, {"REQUEST.md", "baseline.json"})

        request = (folder / "REQUEST.md").read_text(encoding="utf-8")
        self.assertIn("# Review the proposed change ↔", request)
        self.assertEqual(self.read_json("status", "--job", job)["state"], "awaiting_return")
        (folder / "STARTED").mkdir()
        (folder / "RESULT.tmp").write_text("{", encoding="utf-8")
        self.assertEqual(self.read_json("status", "--job", job)["state"], "claimed")

        sha256 = self.return_result(job, files=["notes.md"])
        status = self.read_json("wait", "--job", job)
        self.assertEqual(status["state"], "ready_for_review")
        self.assertEqual(status["result_sha256"], sha256)
        self.assertEqual(status["result"]["files"], ["notes.md"])
        (folder / "REVIEW.md").write_text(
            f"# Review\n\nVerdict: accepted\nResult SHA-256: {sha256}\n", encoding="utf-8"
        )
        status = self.read_json("status", "--job", job)
        self.assertEqual((status["state"], status["verdict"]), ("review_recorded", "accepted"))

    def test_blocked_result_is_available_to_the_reviewer(self):
        job = self.prepare()["job"]
        sha256 = self.return_result(job, outcome="blocked", summary="A required input is missing.")
        status = self.read_json("wait", "--job", job)
        self.assertEqual(status["state"], "blocked")
        self.assertEqual(status["result"]["summary"], "A required input is missing.")
        self.assertEqual(status["result_sha256"], sha256)

    def test_result_rejects_absolute_and_traversing_paths(self):
        job = self.prepare()["job"]
        for path in (str(self.root / "outside.txt"), "../outside.txt", "docs/../../outside.txt"):
            with self.subTest(path=path):
                self.return_result(job, files=[path])
                status = self.read_json("status", "--job", job)
                self.assertEqual(status["state"], "invalid_return")

    def test_result_rejects_a_symlink_that_escapes_the_workspace(self):
        outside = self.root / "outside.txt"
        outside.write_text("Outside the workspace.", encoding="utf-8")
        try:
            (self.workspace / "linked.txt").symlink_to(outside)
        except OSError as error:
            self.skipTest(f"Symlinks unavailable: {error}")
        job = self.prepare()["job"]
        self.return_result(job, files=["linked.txt"])
        self.assertEqual(self.read_json("status", "--job", job)["state"], "invalid_return")

    def test_stale_and_conflicting_reviews_preserve_the_valid_result(self):
        job = self.prepare()["job"]
        review = self.job_path(job) / "REVIEW.md"
        first_sha256 = self.return_result(job)
        review.write_text(
            f"Verdict: accepted\nResult SHA-256: {first_sha256}\n", encoding="utf-8"
        )
        sha256 = self.return_result(job, summary="Revised receipt.")
        self.assertNotEqual(first_sha256, sha256)
        status = self.read_json("status", "--job", job)
        self.assertEqual(status["state"], "ready_for_review")
        self.assertEqual(status["review"], "unmatched_review")
        self.assertEqual(status["result_sha256"], sha256)

        review.write_text(
            f"Verdict: accepted\nVerdict: needs_changes\nResult SHA-256: {sha256}\n",
            encoding="utf-8",
        )
        status = self.read_json("status", "--job", job)
        self.assertEqual(status["state"], "ready_for_review")
        self.assertEqual(status["review"], "unmatched_review")
        self.assertNotIn("verdict", status)

        review.write_bytes(b"\xff")
        status = self.read_json("status", "--job", job)
        self.assertEqual(status["state"], "ready_for_review")
        self.assertEqual(status["review"], "unmatched_review")

    def test_listing_isolates_a_malformed_baseline(self):
        good = self.prepare()["job"]
        bad = "000000000000"
        malformed = self.job_path(bad)
        malformed.mkdir()
        (malformed / "baseline.json").write_text("{", encoding="utf-8")
        statuses = {item["job"]: item for item in self.read_json("status")}
        self.assertEqual(statuses[bad]["state"], "invalid_job")
        self.assertEqual(statuses[good]["state"], "awaiting_return")

    def test_follow_up_links_to_the_selected_prior_job(self):
        prior = self.prepare()["job"]
        self.return_result(prior)
        follow_up = self.prepare("--previous", prior)["job"]
        self.assertNotEqual(prior, follow_up)
        folder = self.job_path(follow_up)
        baseline = json.loads((folder / "baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(baseline["previous_job"], prior)
        self.assertIn(prior, (folder / "REQUEST.md").read_text(encoding="utf-8"))

        other = self.root / "separate workspace"
        other.mkdir()
        process = self.run_helper("prepare", "--previous", prior, workspace=other, brief="Follow up.")
        self.assertNotEqual(process.returncode, 0)

    def test_tracking_outside_the_workspace_fails(self):
        outside = self.root / "outside.txt"
        outside.write_text("Outside the workspace.", encoding="utf-8")
        for path in (str(outside), "../outside.txt"):
            with self.subTest(path=path):
                process = self.run_helper("prepare", "--track", path, brief="Track this.")
                self.assertNotEqual(process.returncode, 0)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Named pipes unavailable")
    def test_tracking_a_named_pipe_fails_without_reading_it(self):
        os.mkfifo(self.workspace / "pipe")
        process = self.run_helper("prepare", "--track", "pipe", brief="Track this.")
        self.assertNotEqual(process.returncode, 0)

    @unittest.skipUnless(shutil.which("git"), "Git unavailable")
    def test_git_baseline_preserves_the_dirty_linked_worktree(self):
        def git(*args, workspace=self.workspace):
            process = subprocess.run(
                ["git", "-C", str(workspace), *args],
                capture_output=True,
                check=False,
                encoding="utf-8",
                timeout=10,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            return process.stdout.strip()

        git("init", "--template=")
        (self.workspace / "tracked.txt").write_bytes(b"original\n")
        git("add", "tracked.txt")
        git(
            "-c", "user.name=Handoff Test",
            "-c", "user.email=handoff-test@example.com",
            "-c", "commit.gpgsign=false",
            "commit", "-m", "Baseline",
        )
        head = git("rev-parse", "HEAD")
        worktree = self.root / "linked worktree"
        git("worktree", "add", "--detach", str(worktree), head)
        (worktree / "tracked.txt").write_bytes(b"staged edit\n")
        git("add", "tracked.txt", workspace=worktree)
        dirty = b"existing unstaged edit\n"
        (worktree / "tracked.txt").write_bytes(dirty)
        (worktree / "user-notes.txt").write_bytes(b"existing notes\n")

        prepared = self.prepare("--track", "tracked.txt", "--track", "future.txt", workspace=worktree)
        folder = worktree / ".agent-handoffs" / prepared["job"]
        baseline = json.loads((folder / "baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(baseline["workspace"], str(worktree))
        self.assertEqual(baseline["git"]["head"], head)
        self.assertIn("MM tracked.txt", baseline["git"]["starting_status"])
        self.assertIn("?? user-notes.txt", baseline["git"]["starting_status"])
        self.assertEqual(
            baseline["files_sha256"],
            {"tracked.txt": hashlib.sha256(dirty).hexdigest(), "future.txt": None},
        )
        self.assertEqual((worktree / "tracked.txt").read_bytes(), dirty)
        staged_paths = git("add", "--dry-run", ".", workspace=worktree)
        self.assertIn("user-notes.txt", staged_paths)
        self.assertNotIn(".agent-handoffs", staged_paths)


if __name__ == "__main__":
    unittest.main()
