# kindle-vocab

Serves your saved vocabulary in JSON format from your USB-connected Kindle.

## Getting Started

Install `uv` via Homebrew if you don't yet have it: `brew install uv`. There are no dependencies outside of the stdlib at the moment but this will get the correct Python version and all set up.

1. `uv venv`
2. `uv pip sync pyproject.toml`
3. `uv run python main.py`

You should see some messages about waiting for a Kindle or serving at a URL depending on your setup. Default will be at http://localhost:11000.