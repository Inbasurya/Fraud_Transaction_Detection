"""Centralised application configuration — re-exports from the canonical config."""

from __future__ import annotations

from app.config import Settings, settings

__all__ = ["Settings", "settings"]
