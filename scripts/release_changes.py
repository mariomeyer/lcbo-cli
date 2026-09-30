"""Emit a GitHub Actions output deciding whether a push changed more than docs."""
import argparse
import subprocess
from pathlib import PurePosixPath


def release_relevant_changes(base: str, head: str) -> bool:
    if base and set(base) == {"0"}:
        base = subprocess.check_output(
            ["git", "hash-object", "-w", "-t", "tree", "--stdin"],
            input=b"",
        ).decode().strip()
    paths = subprocess.check_output([
        "git", "diff", "--no-renames", "--name-only", "-z", base, head,
    ]).decode("utf-8", errors="surrogateescape").split("\0")
    for filename in filter(None, paths):
        path = PurePosixPath(filename)
        if (path.parts[0] == "docs"
                or path.suffix.lower() in {".md", ".rst", ".adoc"}
                or filename == "scripts/readme_screenshots.py"):
            continue
        return True
    return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    print(f"release_relevant={str(release_relevant_changes(args.base, args.head)).lower()}")
