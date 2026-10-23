"""Configuração de runtime do PandaNews.

Resolve a raiz estável do runtime (mesma lógica do CLI em Node):
PANDANEWS_HOME -> ~/.pandanews. Carrega .env quando presente.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: S110 - .env é opcional
    pass


def resolve_home() -> Path:
    env = os.environ.get("PANDANEWS_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".pandanews"


HOME = resolve_home()
DATA_DIR = HOME / "data"
IMAGES_DIR = DATA_DIR / "imagens"
DB_PATH = DATA_DIR / "pandanews.db"
DB_URL = os.environ.get("PANDANEWS_DB_URL", f"sqlite:///{DB_PATH}")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

DEFAULT_LLM_BASE_URLS = {
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta/openai",
}
DEFAULT_LLM_MODELS = {
    "nvidia": "meta/llama-3.3-70b-instruct",
    "google": "gemini-3.8-flash",
}
