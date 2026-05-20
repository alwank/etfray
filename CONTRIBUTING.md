# Contributing to etfray

## Development Setup

```bash
git clone https://github.com/alwank/etfray.git
cd etfray
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"
```

## Running Tests

```bash
pytest
```

## Code Style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .
ruff format .
```

## Pull Requests

1. Fork the repo and create a feature branch from `main`
2. Add tests for new functionality
3. Ensure `pytest` and `ruff check` pass
4. Keep commits focused and write clear commit messages
5. Open a PR with a description of what changed and why

## Reporting Issues

Open an issue at https://github.com/alwank/etfray/issues with:

- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
