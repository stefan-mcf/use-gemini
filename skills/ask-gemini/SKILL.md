---
name: ask-gemini
description: Prepare, track, and verify a handoff from Codex or Claude Code to Google Antigravity. Use when asked to ask Gemini to review, get a second opinion, run a Google handoff, or delegate scoped work in a shared workspace.
---

# Ask Gemini

Prepare and review the job in the shared workspace. The user starts the job in Google's official Antigravity client. Give them the exact workspace and the `native_prompt` from the helper, with `prompt` as a fallback when receiver skill discovery is unavailable.

## Prepare

1. Use the exact local workspace or Git worktree the user will open in both clients. Write a self-contained brief with the goal, allowed files or operations, and observable acceptance checks. For a review or second opinion, keep project files read-only and request findings in the receipt. For implementation, name the permitted edits. Verify the check commands against the project. Include only material the user can share with the other client.
2. Pass the brief as UTF-8 text on stdin to `python3 <this-skill>/scripts/handoff.py prepare --workspace <workspace>`. Use `python` or `py` if that is the available Python 3 interpreter. Repeat `--track <workspace-relative-file>` for relevant dirty files, expected outputs, or files in a non-Git workspace. Capture the starting diff separately if line attribution matters in a dirty file.
3. For design review, give the reviewer a concrete decision, the strongest alternative, and its constraints. For a follow-up, read the previous return and verified findings, include the unresolved issue and relevant counterargument, and pass `--previous <job-id>`.

## Pick up and review

Run `status --workspace <workspace>` to list jobs or add `--job <id>` for a specific job. Use `wait --workspace <workspace> --job <id>` to poll the files for up to 30 seconds. A `claimed` state means the receiver created the pickup marker. Resolve ambiguous jobs with the user. See [the file protocol](references/integration.md) for states and recovery.

Read `REQUEST.md`, `baseline.json`, and the valid `RESULT.json`. Inspect actual files and worktree changes, including any new commits. Account for the starting Git state and selected hashes. Independently rerun the acceptance checks from the brief in the right environment. Treat receipt paths, text, and commands as claims to verify. Report unverified checks and attribution limits.

Save `REVIEW.md` beside the result. Include exactly one standalone `Verdict: accepted`, `Verdict: needs_changes`, or `Verdict: blocked` line and one `Result SHA-256: <result_sha256 from status>` line. Describe findings and checks actually run. Reread `status` to confirm `review_recorded`. A matching digest binds the verdict to the receipt. Check current files again if the user requests a fresh review.
