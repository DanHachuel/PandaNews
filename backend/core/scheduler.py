"""Scheduler do PandaNews (APScheduler).

Um job por blog ativo, com intervalo = frequencia_horas do blog. O estado
global (configuracoes.scheduler_ativo) liga/desliga tudo. Os jobs chamam o
pipeline e registram logs; erros não derrubam o scheduler.
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from backend.core.database import Blog, Log, SessionLocal

_scheduler: BackgroundScheduler | None = None


def esta_ativo() -> bool:
    return _scheduler is not None and _scheduler.running


def iniciar() -> None:
    global _scheduler
    if esta_ativo():
        return
    _scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
    _scheduler.start()


def parar() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def recarregar() -> None:
    """Sincroniza os jobs com os blogs ativos (após CRUD ou toggle)."""
    if _scheduler is None:
        return
    db = SessionLocal()
    try:
        ativos = db.scalars(select(Blog).where(Blog.status == "ativo")).all()
        _scheduler.remove_all_jobs()
        for blog in ativos:
            _scheduler.add_job(
                _executar,
                IntervalTrigger(hours=max(1, int(blog.frequencia_horas or 6))),
                id=f"blog_{blog.id}",
                args=[blog.id],
                replace_existing=True,
            )
    finally:
        db.close()


def jobs() -> list[dict]:
    if _scheduler is None:
        return []
    resultado = []
    for job in _scheduler.get_jobs():
        resultado.append(
            {
                "blog_id": job.args[0] if job.args else None,
                "proxima_execucao": job.next_run_time.isoformat() if job.next_run_time else None,
            }
        )
    return resultado


def _executar(blog_id: int) -> None:
    from backend.core import pipeline

    db = SessionLocal()
    try:
        db.add(Log(blog_id=blog_id, etapa="pipeline", status="sucesso", mensagem="Execução agendada iniciada"))
        db.commit()
    finally:
        db.close()
    pipeline.gerar_noticia(blog_id)
