"""PandaNews API — FastAPI.

Fase 0/1: aplicação mínima com endpoint de health e CORS liberado para a UI
local (127.0.0.1:3030). CRUD de blogs e configurações chegam na Fase 1.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PandaNews API", version="0.1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3030", "http://127.0.0.1:3030"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "pandanews", "version": app.version}
