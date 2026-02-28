"""
Main entry point for BotSalinha.

Delegates execution to the new Typer-based Developer CLI.
"""

from .core.cli import main

if __name__ == "__main__":
    main()
