# Contributing to etfray

Thank you for your interest in contributing to etfray! This guide covers everything you need to get started — whether you're fixing a bug, improving documentation, or adding a new feature.

## Development Setup

```bash
git clone https://github.com/alwank/etfray.git
cd etfray
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"
```

Requires Python 3.11+.

## Codebase Orientation

etfray follows a three-layer architecture:

| Layer | Directory | Responsibility |
|-------|-----------|----------------|
| Data | `etfray/data/` | External I/O — SEC EDGAR, Yahoo Finance, IBKR, web scraping. Handles fetching and caching. |
| Domain | `etfray/domain/` | Pure computation — analytics, formatting, no I/O. |
| UI | `etfray/ui/` | Textual TUI views and components. |

Other key locations:

- `etfray/db/database.py` — SQLite layer (settings, cache, watchlists)
- `tests/` — pytest test suite
- `docs/` — MkDocs documentation source

For a detailed breakdown of services, data flow, and design decisions, see the [Architecture Guide](docs/developer/architecture.md).

## Branching Workflow

This project uses **Gitflow**:

```
main ─────────────────────────────────── stable releases
  │
  └── develop ────────────────────────── integration branch
        │
        ├── feature/my-feature ───────── new features
        ├── release/0.3.0 ────────────── release prep
        │
main ←── hotfix/critical-fix ─────────── urgent production fixes
```

### Branch rules

| Branch | Created from | Merges into | Purpose |
|--------|-------------|-------------|---------|
| `feature/*` | `develop` | `develop` | New features and enhancements |
| `release/*` | `develop` | `main` and `develop` | Version bump, final fixes before release |
| `hotfix/*` | `main` | `main` and `develop` | Critical fixes to the current release |

### For contributors

1. Fork the repository
2. Create your branch from `develop`:
   ```bash
   git checkout develop
   git checkout -b feature/my-feature
   ```
3. Make your changes, commit, and push to your fork
4. Open a PR targeting `develop`

For hotfixes (critical bugs in the current release), branch from `main` and target your PR to `main`.

## Making Changes

1. Create a branch following the naming convention above
2. Write focused commits with clear messages
3. Add or update tests for any new functionality
4. Ensure all checks pass before opening a PR:
   ```bash
   ruff check .
   ruff format --check .
   pytest
   ```

## Documentation Contributions

Documentation improvements are welcome — typo fixes, better examples, new guides, or clarifications.

### What lives where

```
docs/
├── getting-started/    # Installation, quickstart
├── user-guide/         # Feature-specific guides
├── tutorials/          # Step-by-step walkthroughs
├── developer/          # Architecture, contributing
└── assets/             # Screenshots and images
```

### Building docs locally

```bash
mkdocs serve
```

Then open http://localhost:8000 to preview your changes.

### Guidelines

- Keep language concise and direct
- Add screenshots for UI-related changes (save to `docs/assets/`)
- Follow existing page structure and tone
- Documentation PRs also target `develop`

## Running Tests

```bash
pytest
```

Tests live in `tests/` and use pytest. If your change touches analytics or data logic, add corresponding test coverage.

## Code Style

This project uses [Ruff](https://docs.astral.sh/ruff/) (line length 120):

```bash
ruff check .
ruff format .
```

- Python 3.11+ type hints throughout
- Imports sorted by Ruff (`isort` rules)

## Pull Request Process

1. Ensure CI passes (lint + tests on Python 3.11 and 3.12)
2. Target `develop` for features and docs; target `main` only for hotfixes
3. Write a clear PR description:
   - What changed and why
   - How to test it
   - Any breaking changes or migration notes
4. Keep PRs focused — one logical change per PR

## Reporting Issues

Open an issue at https://github.com/alwank/etfray/issues with:

- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
- Relevant error output or screenshots
