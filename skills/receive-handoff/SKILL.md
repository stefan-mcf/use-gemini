---
name: receive-handoff
description: Receive a user-started handoff in Google Antigravity from a shared workspace. Use a supplied job ID or request path to pick up a local brief and return a receipt to the originating agent.
---

# Receive a handoff

Use the ID from `/receive-handoff <id>` or the explicit request path. Open `.agent-handoffs/<id>/REQUEST.md` in the current workspace. Confirm the job ID and workspace match `baseline.json` before acting. If the request is missing or the job is ambiguous, ask for the exact folder and ID.

If `RESULT.json` exists, report the saved outcome. Otherwise claim the job with a single `mkdir` of the sibling `STARTED` directory that fails if it already exists. On an existing marker, resume only when the user explicitly asks to resume this job and confirms the original session has stopped. Keep the marker in place.

Carry out the brief within scope and respect workspace instructions. For read-only review, put findings in the receipt and leave project files untouched. Run the brief's checks. Use the result schema in the request and record actual work, files, checks, and blockers. Use workspace-relative filenames with forward slashes. Write `RESULT.tmp` beside the brief and rename it to `RESULT.json` when finished. Tell the user the job ID and outcome so they can return to the originating agent for verification.
