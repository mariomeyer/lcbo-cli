# Releases and PyPI setup

The distribution is **lcbo**. The repository is **mariomeyer/lcbo-cli**, the import is `lcbo_cli`, and the console command is `lcbo`.

The package is [published on PyPI](https://pypi.org/project/lcbo/), and this repository's automatic releases are enabled. The setup instructions below are for maintainers configuring or restoring the publisher, not prerequisites for using the CLI.

## Workflow

`.github/workflows/release.yml` runs on pull requests, main pushes, and manual dispatch:

1. Offline tests run on Python 3.11, 3.12, 3.13, and 3.14.
2. The build job creates wheel/source distributions, runs strict Twine checks, smoke-tests the wheel's `lcbo --help`, and uploads build artifacts.
3. With repository variable `RELEASE_ENABLED=true`, eligible successful main runs use pinned Python Semantic Release to calculate the next version from commits, update `pyproject.toml` and `uv.lock`, generate `CHANGELOG.md`, and create a tag and GitHub release with distribution assets. Documentation-only pushes skip this job entirely, regardless of commit message.
4. Only when a new version was released, a separate `pypi` job downloads those exact release artifacts and publishes using OIDC Trusted Publishing. It has no checkout/build step and no long-lived PyPI token.

PR jobs have read-only permissions and no persistent checkout credentials. Only the release job has `contents: write`; only the publisher has `id-token: write`. Actions are pinned to commit SHAs. The release job serializes main releases and refuses to release a commit if main moved after its tests started. Release commits use `chore(release): VERSION [skip ci]`, preventing loops.

The path guard compares the complete push range, not just the last commit. It treats `docs/`, Markdown/reStructuredText/AsciiDoc files, and `scripts/readme_screenshots.py` as documentation. Source deletions and mixed source/docs pushes remain eligible. Unknown or invalid Git ranges fail the build rather than authorizing publication. Manual dispatch is an explicit release request and bypasses the docs-only push check; Conventional Commits still determine whether a new version exists.

## One-time setup

For a new deployment, leave `RELEASE_ENABLED` unset or `false` until these steps are complete. This repository has already completed setup. No PyPI project or Trusted Publisher is created merely by adding the workflow.

1. Sign into your own [PyPI account](https://pypi.org/) with two-factor authentication. If `lcbo` does not exist, add a [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/). If you already own it, add a publisher to the existing project. A missing public package page does not guarantee the name can be registered; verify this in PyPI before enabling releases.
2. Use these exact publisher settings:

   | Setting | Value |
   | --- | --- |
   | PyPI project | `lcbo` |
   | GitHub owner | `mariomeyer` |
   | Repository | `lcbo-cli` |
   | Workflow filename | `release.yml` |
   | Environment | `pypi` |

3. The repository's `pypi` environment is configured to allow only `main`, without required reviewers, for automatic publishing. Verify this under GitHub Settings → Environments before enabling releases. If setting up another repository, create the environment with the same restriction. If you prefer a manual approval gate, optionally add yourself as a required reviewer; keep self-approval available if you are the only maintainer.
4. Check that branch rules allow the workflow's `GITHUB_TOKEN` to push version commits/tags. If your rules require PRs or signed commits, adapt the release process before enabling it; do not weaken protections or add a broad personal token just to bypass them.
5. Set repository Actions variable `RELEASE_ENABLED` to `true`. Then manually run **CI and Release** on `main`, or push a qualifying Conventional Commit. Publication is automatic unless you opted into environment reviewers.

```sh
gh variable set RELEASE_ENABLED --repo mariomeyer/lcbo-cli --body true
gh workflow run release.yml --repo mariomeyer/lcbo-cli --ref main
```

The first published version was 0.1.0. Subsequent calculations start from the latest matching `v{version}` tag. In a fresh repository without tags, Semantic Release starts at 0.0.0; a feature commit produces 0.1.0 with this configuration.

Use the published package:

```sh
uvx lcbo search guinness --limit 5
uv tool install lcbo
```

## Version conventions

| Commit | Effect |
| --- | --- |
| `fix: correct inventory parsing` | Patch |
| `feat: add a product filter` | Minor |
| `feat!: change the JSON schema` | Minor before 1.0; major after 1.0 |
| `docs: clarify usage` / `test:` / `ci:` / `chore:` | No release on their own |

The version in `pyproject.toml` is the package's source of truth. The build hook refreshes only the local project's version in `uv.lock`, stages the lockfile, builds distributions and runs strict Twine validation before the version commit/tag is pushed; it does not intentionally upgrade third-party dependencies. Python Semantic Release also writes the version, changelog, and release commit. Do not hand-edit versions to force a release.

## Recovery and disabling

If the PyPI job fails after the GitHub release succeeded, fix the publisher/environment configuration and **re-run failed jobs** in that same workflow run. This retries the original release artifact without creating another version. Do not re-run all jobs: the release may then be detected as already made, skipping publication. If the original run/artifacts are no longer available, investigate and recover the exact GitHub release files before publishing; do not rebuild an existing published version casually.

If the **release job** fails after pushing its version commit/tag, do not blindly rerun it: main now points at the version commit, so the stale-commit guard will reject that run. First inspect the pushed tag, GitHub release, and `release-distributions` artifact. The artifact is uploaded before attaching GitHub release files, allowing recovery if attachment fails. Reconcile the missing GitHub release/assets from that exact artifact before arranging a targeted publish of that same version; the standard workflow deliberately does not guess a recovery version or bypass its tested-commit guard. If artifact upload itself failed, stop and inspect the runner logs/tag before attempting a rebuild. No automatic release-stage recovery is provided.

PyPI versions cannot be overwritten. Check PyPI before retrying a partially successful upload; the workflow deliberately does not use `skip-existing` to hide mismatched artifacts. Do not delete or move a published version tag.

To disable future releases while keeping CI active:

```sh
gh variable set RELEASE_ENABLED --repo mariomeyer/lcbo-cli --body false
```

This does not cancel already queued jobs; cancel those separately if needed.

Official references: [Python Semantic Release](https://python-semantic-release.readthedocs.io/en/stable/configuration/automatic-releases/github-actions.html), [uv lockfile integration](https://python-semantic-release.readthedocs.io/en/stable/configuration/configuration-guides/uv_integration.html), and [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/).
