"""Processos filhos silenciosos (regra permanente do AGENTS.md).

O PandaNews NUNCA pode abrir janelas de terminal (CMD, PowerShell, console
Python) no computador do usuário. No Windows, todo processo filho precisa da
flag ``CREATE_NO_WINDOW`` (0x08000000); sem ela, qualquer ``subprocess`` ou
gerador de console aloca uma tela preta.

Este módulo é o ÚNICO ponto de entrada autorizado para subprocessos no
backend. Nunca chame ``subprocess.run``/``subprocess.Popen``/``subprocess.call``
nem ``os.system`` diretamente — use ``run_silent_process``/``run_silent``/
``spawn_silent``. O teste ``scripts/test-start-isolation.mjs`` (rodado no CI)
falha o build se encontrar uma chamada direta em ``backend/**/*.py``.

Exemplos::

    from backend.core.proc import run_silent_process, spawn_silent

    # execução síncrona
    run_silent_process(["ffmpeg", "-version"], check=True, capture_output=True)

    # execução assíncrona (não bloqueia o event loop)
    proc = spawn_silent(["pandoc", "--version"])
    proc.wait()

O pipeline de notícias e o APScheduler rodam em memória (threads do
``BackgroundScheduler``), sem processos do sistema operacional — este módulo
só é necessário quando uma ferramenta externa realmente precisa ser chamada.
"""
from __future__ import annotations

import subprocess
import sys

# Flag do Windows: o processo nasce sem console, portanto sem janela visível.
# Ver https://learn.microsoft.com/windows/win32/procthread/process-creation-flags
CREATE_NO_WINDOW = 0x08000000


def silent_kwargs(kwargs: dict | None = None) -> dict:
    """Devolve as opções de subprocesso com a flag de ocultação aplicada.

    Em Windows adiciona ``creationflags=CREATE_NO_WINDOW``; nas demais
    plataformas não há console novo a ocultar, então as opções passam
    intactas. Nunca use ``shell=True`` junto a este helper.
    """
    opts = dict(kwargs or {})
    if sys.platform == "win32":
        opts["creationflags"] = CREATE_NO_WINDOW
    return opts


def run_silent_process(cmd_args, **kwargs):
    """Substitui ``subprocess.run`` — sem janela de console no Windows."""
    return subprocess.run(cmd_args, **silent_kwargs(kwargs))


# Alias: mesma semântica, nome curto para uso interno.
run_silent = run_silent_process


def spawn_silent(cmd_args, **kwargs):
    """Substitui ``subprocess.Popen`` — sem janela de console no Windows."""
    return subprocess.Popen(cmd_args, **silent_kwargs(kwargs))


def call_silent(cmd_args, **kwargs):
    """Substitui ``subprocess.call`` — sem janela de console no Windows."""
    return subprocess.call(cmd_args, **silent_kwargs(kwargs))


def check_output_silent(cmd_args, **kwargs):
    """Substitui ``subprocess.check_output`` — sem janela de console no Windows."""
    return subprocess.check_output(cmd_args, **silent_kwargs(kwargs))


def system_silent(cmd: str) -> int:
    """Substitui ``os.system`` sem abrir shell visível.

    ``os.system`` sempre passa por ``cmd.exe``/``/bin/sh`` e herda o console;
    quando não há alternativa, a chamada é feita pelo helper silencioso.
    """
    if sys.platform == "win32":
        proc = subprocess.run(
            cmd,
            shell=True,
            creationflags=CREATE_NO_WINDOW,
        )
        return proc.returncode
    return subprocess.call(cmd, shell=True)
