# Contributing

See [CONTRIBUTING.md](https://github.com/alwank/etfray/blob/main/CONTRIBUTING.md) in the repository root for full guidelines.

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

## Linting

```bash
ruff check .
ruff format --check .
```

## Building Docs Locally

```bash
mkdocs serve
```

Then open http://localhost:8000.

## Project Conventions

- Python 3.11+ type hints throughout
- Ruff for linting and formatting (line length 120)
- Tests in `tests/` using pytest
- Commits should be focused and descriptive
