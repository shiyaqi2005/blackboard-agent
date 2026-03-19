"""Helpers for bootstrapping local WebArena imports safely."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


_PLACEHOLDER_SITE_URLS: Dict[str, str] = {
    "REDDIT": "http://placeholder.reddit.local",
    "SHOPPING": "http://placeholder.shopping.local",
    "SHOPPING_ADMIN": "http://placeholder.shopping-admin.local",
    "GITLAB": "http://placeholder.gitlab.local",
    "MAP": "http://placeholder.map.local",
    "WIKIPEDIA": "http://placeholder.wikipedia.local",
    "HOMEPAGE": "http://placeholder.homepage.local",
}


def webarena_root() -> Path:
    """Return the checked-out local WebArena repo root."""
    return Path(__file__).resolve().parents[3] / "webarena"


def ensure_placeholder_site_envs() -> None:
    """Seed harmless placeholder site URLs so public-task imports do not crash."""
    for name, value in _PLACEHOLDER_SITE_URLS.items():
        os.environ.setdefault(name, value)
