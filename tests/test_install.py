import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CODEX_SENDER = Path(".agents/skills/ask-gemini")
CLAUDE_SENDER = Path(".claude/skills/ask-gemini")
RECEIVER = Path(".agents/skills/receive-handoff")


class InstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="handoff install ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_install(self, workspace, client=None):
        command = [
            sys.executable,
            str(REPO / "install.py"),
            "--workspace",
            str(workspace),
        ]
        if client is not None:
            command.extend(("--client", client))
        return subprocess.run(command, capture_output=True, timeout=10)

    def assert_installed(self, workspace, expected):
        actual = {
            path.relative_to(workspace)
            for container in (".agents", ".claude")
            for path in (workspace / container / "skills").glob("*")
        }
        self.assertEqual(actual, set(expected))
        for folder in expected:
            source = REPO / "skills" / folder.name / "SKILL.md"
            installed = workspace / folder / "SKILL.md"
            self.assertEqual(installed.read_bytes(), source.read_bytes())

    def test_each_client_installs_its_layout_and_can_repeat(self):
        cases = {
            None: (RECEIVER, CODEX_SENDER),
            "codex": (RECEIVER, CODEX_SENDER),
            "claude": (RECEIVER, CLAUDE_SENDER),
            "both": (RECEIVER, CODEX_SENDER, CLAUDE_SENDER),
        }
        for client, expected in cases.items():
            with self.subTest(client=client):
                workspace = self.root / f"project {client}"
                workspace.mkdir()
                for _ in range(2):
                    result = self.run_install(workspace, client)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assert_installed(workspace, expected)
                for sender in expected[1:]:
                    helper = workspace / sender / "scripts" / "handoff.py"
                    result = subprocess.run(
                        [sys.executable, str(helper), "--help"],
                        cwd=workspace,
                        capture_output=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_both_can_add_claude_to_an_existing_codex_install(self):
        first = self.run_install(self.root)
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_install(self.root, "both")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assert_installed(self.root, (RECEIVER, CODEX_SENDER, CLAUDE_SENDER))

    def test_conflict_in_second_location_prevents_partial_install(self):
        existing = self.root / CLAUDE_SENDER / "SKILL.md"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"existing skill\n")
        result = self.run_install(self.root, "both")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b"Preserving existing skill", result.stderr)
        self.assertEqual(existing.read_bytes(), b"existing skill\n")
        self.assertFalse((self.root / ".agents").exists())

    def test_preserves_and_identifies_previous_skill_folders(self):
        old = [
            self.root / ".agents" / "skills" / name / "SKILL.md"
            for name in ("google-handoff", "codex-handoff")
        ]
        for skill in old:
            skill.parent.mkdir(parents=True)
            skill.write_bytes(b"previous skill\n")
        result = self.run_install(self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"Earlier skill folders", result.stdout)
        for skill in old:
            self.assertEqual(skill.read_bytes(), b"previous skill\n")
            self.assertIn(skill.parent.name.encode(), result.stdout)
        self.assertTrue((self.root / CODEX_SENDER / "SKILL.md").is_file())
        self.assertTrue((self.root / RECEIVER / "SKILL.md").is_file())

    def test_symlinked_location_prevents_install(self):
        outside = self.root / "external configuration"
        outside.mkdir()
        linked = self.root / ".claude"
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symlinks unavailable: {error}")
        result = self.run_install(self.root, "both")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(linked.is_symlink())
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.root / ".agents").exists())
