# file: app/chat_chain.py

"""Legacy CLI entrypoint – moved to app.chain.cli."""

from app.chain.cli import _cli  # noqa: F401

if __name__ == "__main__":  # pragma: no cover
    _cli()
