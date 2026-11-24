# Shared workspace protocol

The helper requires Python 3.9 or later. Its only optional subprocess is Git for the baseline. The user starts Antigravity in the exact same local folder or worktree and submits the prompt in the official client. Select the account and model in that client. [Antigravity quickstart](https://antigravity.google/docs/cli-getting-started) · [Antigravity skills](https://antigravity.google/docs/skills) · [Antigravity FAQ](https://antigravity.google/docs/faq/)

## Files

Jobs live in `.agent-handoffs/<12-character job ID>/`. `REQUEST.md` carries the scope, workspace path, and self-contained return instructions. `baseline.json` records the workspace, job identity, selected file hashes (`null` for absent files), and available starting Git metadata. With `--previous`, it identifies the prior job in the same workspace. The helper adds an ignore file inside `.agent-handoffs/` when absent. Review what you stage for Git, especially if handoff files were previously tracked.

The receiver claims a job through a single `mkdir` of `STARTED` that fails if the marker already exists. It writes `RESULT.tmp` in the job folder and renames it to `RESULT.json` after the work and checks finish. The result contains `job`, `outcome` (`completed` or `blocked`), a nonempty `summary`, and string arrays `files` and `checks`. Use workspace-relative file paths with forward slashes. Use empty arrays for a text review with no changed project files or commands.

## States

| State | Next action |
| --- | --- |
| `awaiting_return` | Give the user the exact workspace and prompt. |
| `claimed` | Wait for the receipt. If the session stopped, have the user confirm before resuming the same job with the marker in place. |
| `ready_for_review` | Review the actual work and run the brief's checks. |
| `blocked` | Inspect any partial work and record the blocker. |
| `invalid_job` or `invalid_return` | Read the reason, verify the workspace and data, and obtain a corrected receipt or fresh job as appropriate. |
| `review_recorded` | Read the saved verdict. Rerun checks if the current work has changed. |

`unmatched_review` means a saved review could not be read or bound to the current receipt. Recheck the work and make a new review when requested. A baseline records starting status and the files expressly tracked. For exact attribution of overlapping changes, use a clean worktree or retain the relevant starting diff. A pickup marker records a past claim. Confirm the prior Antigravity session has stopped before resuming so two sessions cannot write simultaneously.
