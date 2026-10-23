"""PandaNews API — FastAPI.

Fase 0 (0.1.00): aplicação mínima com endpoint de health.
Fase 1: CRUD de blogs, configurações e router de LLM (NVIDIA NIM -> Google Gemini).
"""
from fastapi import FastAPI

app = FastAPI(title="PandaNews API", version="0.1.00")


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "pandanews", "version": app.version}
