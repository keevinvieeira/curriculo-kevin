"""Dated status history for applications.json.

`status` stays the current value (the app, dashboards and tracking read it as before);
`status_history` records every transition as ``{status, date, source, note}``.
Dates are ISO (YYYY-MM-DD) or ``None`` when the day was never recorded — the
migration never invents one.

Writers call ``set_status`` when they change a status, and ``sync_history`` before
saving as a safety net: any status change that bypassed ``set_status`` still gets a
history entry, dated the day it was saved.
"""

from __future__ import annotations

import datetime
import unicodedata
from typing import Any, Optional

STATUSES = ["Candidatado", "Triagem", "Entrevista", "Proposta", "Rejeitado", "Desistente"]
_RANK = {status: n for n, status in enumerate(STATUSES)}
_DONE_STAGE_STATUSES = {"Concluído", "Em andamento", "Encerrado"}


def _today() -> str:
    return datetime.date.today().isoformat()


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _stage_status(stage_name: str) -> Optional[str]:
    """Map a free-text checklist stage to the general status it evidences."""
    name = _fold(stage_name)
    if "negativa" in name:
        return "Rejeitado"
    if "proposta" in name or "offer" in name:
        return None  # "RH / Proposta" encerrado != proposta recebida; only an explicit status says so
    if "entrevista" in name:
        return "Entrevista"
    if "triagem" in name or "screening" in name or "teste" in name:
        return "Triagem"
    return None


def derive_history(app: dict[str, Any]) -> list[dict[str, Any]]:
    """Reconstruct a history from what the record already holds (date_applied, dated
    checklist stages, date_rejected). Only statuses the record actually reached are
    included, each with the earliest date evidenced for it (or None)."""
    current = app.get("status")
    reached: dict[str, Optional[str]] = {"Candidatado": app.get("date_applied") or None}
    undated_stage: set[str] = set()

    for stage in app.get("stages") or []:
        status = _stage_status(stage.get("name", ""))
        if not status or stage.get("status") not in _DONE_STAGE_STATUSES:
            continue
        # A checklist can run ahead of the general status; trust the general status.
        if _RANK[status] > _RANK.get(current, 0):
            continue
        date = stage.get("date") or None
        if date is None:
            undated_stage.add(status)
        if status not in reached or (date and (reached[status] is None or date < reached[status])):
            reached[status] = date

    if current and current not in reached:
        reached[current] = None
    if current == "Rejeitado" and app.get("date_rejected"):
        reached["Rejeitado"] = app["date_rejected"]

    ordered = sorted(reached, key=lambda status: _RANK.get(status, len(STATUSES)))
    history = [{"status": status, "date": reached[status], "source": "migration"} for status in ordered]
    for entry in history:
        if entry["date"] is None:
            entry["note"] = "data não registrada no histórico original"
        elif entry["status"] in undated_stage:
            entry["note"] = "data mais antiga registrada; houve etapa anterior sem data"
    return history


def set_status(app: dict[str, Any], status: str, *, date: Optional[str] = None,
               source: str = "manual", note: str = "") -> dict[str, Any]:
    """Change the current status and append the transition. No-op if unchanged."""
    history = app.setdefault("status_history", derive_history(app) if "status" in app else [])
    if history and history[-1]["status"] == status and app.get("status") == status:
        return app
    entry: dict[str, Any] = {"status": status, "date": date or _today(), "source": source}
    if note:
        entry["note"] = note
    history.append(entry)
    app["status"] = status
    return app


def sync_history(app: dict[str, Any], *, source: str = "sync") -> dict[str, Any]:
    """Ensure status_history exists and ends in the current status."""
    if "status_history" not in app:
        app["status_history"] = derive_history(app)
    history = app["status_history"]
    if app.get("status") and (not history or history[-1]["status"] != app["status"]):
        history.append({"status": app["status"], "date": _today(), "source": source})
    return app


def new_history(applied_date: str, source: str) -> list[dict[str, Any]]:
    return [{"status": "Candidatado", "date": applied_date, "source": source}]
