# Use Gemini

[![CI](https://github.com/stefan-mcf/use-gemini/actions/workflows/ci.yml/badge.svg)](https://github.com/stefan-mcf/use-gemini/actions/workflows/ci.yml) [![MIT license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Get a second opinion from Gemini or give it a coding task. Start in **Codex** or **Claude Code**, run the brief in **Google Antigravity**, and review the result in your original client. Both clients open the same local workspace.

> Use Gemini for a second opinion on this plan. Review only.

```text
Codex or Claude Code → brief → you start it in Antigravity → result → review
```

The sender prepares a scoped brief and checks the return against the actual files. You choose Gemini and start the job in Antigravity. For a second pass, the sender can link a new brief to the previous result. [Antigravity model guide](https://antigravity.google/docs/models)

## Install

You need Python 3.9 or newer, Codex or Claude Code, and Google's official Antigravity app or CLI. Git helps with reviewing code changes. [Codex skills](https://learn.chatgpt.com/docs/build-skills) · [Claude Code skills](https://code.claude.com/docs/en/skills) · [Antigravity quickstart](https://antigravity.google/docs/cli-getting-started)

To try both sender clients, run this in the parent directory of a new demo workspace.

```sh
git clone https://github.com/stefan-mcf/use-gemini.git
mkdir use-gemini-demo
python3 use-gemini/install.py --workspace use-gemini-demo --client both
```

| Start from | Install option | Command in that client |
| --- | --- | --- |
| Codex | `--client codex` (default) | `$use-gemini` |
| Claude Code | `--client claude` | `/use-gemini` |
| Either client | `--client both` | Both commands above |

Use your project path after `--workspace` to install into an existing project. On Windows, use `py -3` if needed. You can download and extract the source ZIP in place of cloning. The installer reports conflicting copies before writing and leaves your existing skills in place. If an open client needs to refresh its skills, restart it or run `/skills reload` in Antigravity. [Antigravity skill discovery](https://antigravity.google/docs/skills)

## Try it

1. Open the demo workspace in Codex or Claude Code. Say “Use Gemini to review this README outline for gaps. Review only.” Or try a scoped change such as “Use Gemini to create `greeting.txt` with one line, `Hello from Gemini.` Check the exact line and change only that file.” You can prefix either prompt with your client's command from the table.
2. Open that same directory or Git worktree in Antigravity and select a Gemini model. Submit `/receive-handoff <job-id>` using the ID your first client gives you. If the command is unavailable, paste the plain prompt it supplies.
3. Back in the first client, say “Verify handoff `<job-id>`.” It checks the returned receipt, the actual files, and any acceptance checks from the brief, then saves a review.

Each job lives under `.agent-handoffs/`. The sender saves the request and starting state. Antigravity records the result. The sender records what it verified in `REVIEW.md`. The helper adds a Git ignore file when absent. [File protocol and recovery](skills/use-gemini/references/integration.md)

## Validation

Run `python3 -m unittest discover -s tests -v` to check the installer and local file workflow. CI runs these checks on Linux, macOS, and Windows without provider accounts. The walkthrough above runs the interactive handoff in your clients. [Field notes](docs/field-notes.md) · [Packaging decision](docs/packaging.md)

## License

[MIT](LICENSE)
