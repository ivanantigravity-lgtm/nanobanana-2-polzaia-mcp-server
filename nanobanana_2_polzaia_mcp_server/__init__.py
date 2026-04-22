"""Nano Banana 2 Polza MCP Server."""

__version__ = "0.5.1"
__author__ = "ivanantigravity-lgtm"
__email__ = "team@nanobanana.dev"
__description__ = "Nano Banana MCP server backed by Polza media and storage APIs"

from .server import create_app, create_wrapper_app, main

__all__ = ["create_app", "create_wrapper_app", "main"]
