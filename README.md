# Codex ↔ Antigravity Handoff

Get a second opinion or hand a scoped task from Codex to Google Antigravity in the same local workspace. Codex writes the brief, you submit it in Antigravity, and Codex looks at the actual work and reruns the agreed checks. For another round, Codex can link the new brief to the previous receipt.

```text
Codex → REQUEST.md → you start the job in Antigravity → RESULT.json → Codex review
```

The package includes two Agent Skills and a local Python helper. Sign in and choose the model in each official client. The helper uses the shared filesystem for the handoff. [Packaging decision](docs/packaging.md) · [Pre-release field notes](docs/field-notes.md)

## Install

You need Codex, Google's official Antigravity app or CLI, and Python 3.9 or newer. Git is recommended for code handoffs. [Codex skills](https://learn.chatgpt.com/docs/build-skills) · [Antigravity quickstart](https://antigravity.google/docs/cli-getting-started)

Try it in a fresh directory from a terminal in its parent directory.

```sh
git clone https://github.com/stefan-mcf/codex-antigravity-handoff.git
mkdir handoff-demo
python3 codex-antigravity-handoff/install.py --workspace handoff-demo
```

On Windows, use `py -3` in place of `python3` if needed. You can download and extract the repository ZIP in place of cloning. For an existing project, use its path after `--workspace`. The installer copies both skills into `.agents/skills/` in that workspace and reports any conflicting copies before writing either skill. You can also copy the `skills/google-handoff` and `skills/codex-handoff` directories to that location yourself. Reopen Codex to pick up the installed skills if needed. In a running Antigravity CLI use `/skills reload`. [Antigravity skill discovery](https://antigravity.google/docs/skills)

## Try a round trip

1. Open `handoff-demo` in Codex and enter this request.

   ```text
   $google-handoff Prepare a task for Antigravity. Create greeting.txt containing
   exactly one line, Hello from Antigravity. Track greeting.txt before the handoff.
   The acceptance check is reading the file back and verifying that exact line.
   ```

2. Open the same directory or Git worktree in Antigravity. Submit `/codex-handoff <job-id>` using the exact job ID Codex gives you. If the receiver skill is unavailable, paste the plain prompt Codex provides instead. The brief includes the return instructions.
3. When Antigravity returns, ask Codex, `Review the Google handoff <job-id>.` Codex reads the returned receipt, independently checks `greeting.txt`, and writes `REVIEW.md` with a verdict. If you want a follow-up, ask Codex to prepare another brief linked to that job.

Each job has its own folder under `.agent-handoffs/`. A pickup marker records that Antigravity claimed the job. A return receipt reports what Antigravity did. The review records what Codex verified. The helper adds a Git ignore file inside the job store when absent. Review staged files before sharing a repository. [File protocol and recovery](skills/google-handoff/references/integration.md)

## Validation

From this repository, run the local tests with `python3 -m unittest discover -s tests -v`. They cover the job lifecycle, dirty Git worktrees, unsafe receipt paths, stale or conflicting verdicts, and linked follow-ups. CI also exercises installer and helper behavior on its platform matrix. These checks run without either account. The walkthrough above exercises the live client handoff.

## License

[MIT](LICENSE)
