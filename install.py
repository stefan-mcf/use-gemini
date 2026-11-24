"""Install both handoff skills in a shared project directory."""

import argparse
import shutil
from pathlib import Path

SKILLS = ("google-handoff", "codex-handoff")
IGNORE_CACHE = shutil.ignore_patterns("__pycache__", "*.pyc")


def is_plain_directory(path):
    return path.is_dir() and not path.is_symlink() and path.resolve() == path


def contents(root):
    """Read an installable skill tree, including its empty directories."""
    files = {}
    directories = [root]
    while directories:
        directory = directories.pop()
        entries = list(directory.iterdir())
        ignored = IGNORE_CACHE(directory, [entry.name for entry in entries])
        for entry in entries:
            if entry.name in ignored:
                continue
            relative = entry.relative_to(root)
            if is_plain_directory(entry):
                files[relative] = None
                directories.append(entry)
            elif entry.is_file() and not entry.is_symlink():
                files[relative] = entry.read_bytes()
            else:
                raise ValueError(f"Invalid skill file or directory at {entry}")
    return files


def install(workspace):
    workspace = workspace.expanduser().resolve(strict=True)
    if not workspace.is_dir():
        raise ValueError(f"Expected an existing workspace directory at {workspace}")

    source_root = Path(__file__).resolve().parent / "skills"
    agents = workspace / ".agents"
    destination = agents / "skills"
    for directory in (agents, destination):
        present = directory.exists() or directory.is_symlink()
        if present and not is_plain_directory(directory):
            raise ValueError(
                f"Preserving {directory}. Choose a workspace with a regular skills directory."
            )

    pending = []
    for name in SKILLS:
        source = source_root / name
        if not is_plain_directory(source) or not (source / "SKILL.md").is_file():
            raise ValueError(f"Missing packaged skill at {source}")
        expected = contents(source)
        target = destination / name
        if not target.exists() and not target.is_symlink():
            pending.append((source, target))
        elif not is_plain_directory(target) or contents(target) != expected:
            raise ValueError(
                f"Preserving existing skill at {target}. Move it aside to install this version."
            )

    destination.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        # Reserve both names before copying so another install cannot overwrite either one.
        for _, target in pending:
            target.mkdir()
            created.append(target)
        for source, target in pending:
            shutil.copytree(source, target, dirs_exist_ok=True, ignore=IGNORE_CACHE)
    except BaseException:
        # Only roll back directories created during this invocation.
        for target in reversed(created):
            shutil.rmtree(target)
        raise
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace", required=True, type=Path, help="existing project directory"
    )
    args = parser.parse_args()
    try:
        destination = install(args.workspace)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Both skill folders are present in {destination}")


if __name__ == "__main__":
    main()
