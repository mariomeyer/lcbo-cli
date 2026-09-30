import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_changes.py"


@pytest.fixture
def repository(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init", "--quiet", "-b", "main")
    git("config", "user.name", "Release Test")
    git("config", "user.email", "test@example.invalid")
    git("config", "commit.gpgsign", "false")
    git("config", "core.hooksPath", "/dev/null")
    (tmp_path / "README.md").write_text("Initial documentation\n")
    git("add", ".")
    git("commit", "--quiet", "-m", "docs: initial documentation")
    return tmp_path, git


def check(repository, base, head="HEAD"):
    path, _ = repository
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--base", base, "--head", head],
        cwd=path, capture_output=True, text=True,
    )


@pytest.mark.parametrize("filename", [
    "README.md", "docs/images/search.svg", "docs/reference.md",
    "scripts/readme_screenshots.py", "guide.rst",
])
def test_docs_only_changes_do_not_release_even_with_feat_message(repository, filename):
    path, git = repository
    base = git("rev-parse", "HEAD")
    target = path / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Changed documentation\n")
    git("add", ".")
    git("commit", "--quiet", "-m", "feat: improve documentation")
    result = check(repository, base)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "release_relevant=false"


def test_mixed_push_considers_all_commits_not_only_the_last(repository):
    path, git = repository
    base = git("rev-parse", "HEAD")
    (path / "application.py").write_text("value = 1\n")
    git("add", ".")
    git("commit", "--quiet", "-m", "feat: add application")
    (path / "README.md").write_text("Updated documentation\n")
    git("add", ".")
    git("commit", "--quiet", "-m", "docs: update readme")
    result = check(repository, base)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "release_relevant=true"


@pytest.mark.parametrize("operation", ["delete", "move_to_docs"])
def test_source_removal_is_release_relevant(repository, operation):
    path, git = repository
    (path / "application.py").write_text("value = 1\n")
    git("add", ".")
    git("commit", "--quiet", "-m", "feat: add application")
    base = git("rev-parse", "HEAD")
    if operation == "delete":
        (path / "application.py").unlink()
    else:
        (path / "docs").mkdir()
        (path / "application.py").rename(path / "docs" / "example.py")
    git("add", "--all")
    git("commit", "--quiet", "-m", "fix: remove application")
    result = check(repository, base)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "release_relevant=true"


def test_initial_documentation_only_push_does_not_release(repository):
    result = check(repository, "0" * 40)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "release_relevant=false"


def test_invalid_base_fails_closed(repository):
    result = check(repository, "missing-commit")
    assert result.returncode != 0
    assert "release_relevant=true" not in result.stdout
