"""Compatibility entry point; the frontend only calls OpenFaaS over HTTP."""

from cofrap.frontend.main import app, create_app

__all__ = ["app", "create_app"]
