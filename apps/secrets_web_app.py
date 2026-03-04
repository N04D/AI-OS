"""Local web UI for AI-OS secrets management."""

from aios.secrets.ui.routes import create_app

app = create_app()
