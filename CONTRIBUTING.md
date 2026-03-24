# Contributing to NeverOnce

Thanks for your interest in contributing to NeverOnce!

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/neveronce.git
   cd neveronce
   ```
3. Install in development mode:
   ```bash
   pip install -e ".[mcp]"
   ```

## Running Tests

```bash
python -m pytest tests/ -v
```

All tests must pass on Python 3.10, 3.11, 3.12, and 3.13 across Ubuntu, Windows, and macOS.

## Development Guidelines

- **Zero dependencies** — NeverOnce uses only the Python standard library. Do not add third-party dependencies to the core package.
- **Keep it simple** — the entire library is ~400 lines. Contributions should maintain this simplicity.
- **Corrections-first** — any change to memory retrieval must preserve the guarantee that corrections always surface first and never decay.
- **SQLite-backed** — all persistence goes through SQLite. No alternative backends.

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for any new functionality
3. Ensure all existing tests still pass
4. Update the README if your change affects the public API
5. Submit a PR with a clear description of what and why

## Code Style

- Follow PEP 8
- Use type hints where practical
- Keep functions focused and small
- Docstrings for public methods

## Reporting Bugs

Open a GitHub issue with:
- Python version and OS
- Steps to reproduce
- Expected vs actual behavior
- Error traceback if applicable

## Security Issues

See [SECURITY.md](SECURITY.md) for reporting security vulnerabilities. Do not open public issues for security bugs.
