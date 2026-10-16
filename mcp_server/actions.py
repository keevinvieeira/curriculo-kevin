"""Write actions behind the Career OS MCP tools (Fase 2).

Every write goes through a deterministic gate first: adaptations through
grounding.validate_adaptation, applications through the status vocabulary and a
duplicate check. Nothing here submits anything to an employer.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from application_history import STATUSES, set_status
from engine.automation import tracking
from engine.automation.dedupe import find_duplicate
from grounding import validate_adaptation
from job_store import LANGUAGES, ROOT, SCHEMA_VERSION, job_path, load_job, read_json, slugify, write_json

MASTER_PATH = ROOT / "master_resume.json"
EXPORTS_DIR = ROOT / "exports" / "curriculos_vagas"
TEMPLATE = ROOT / "templates" / "resume_theme.html"


def _master() -> dict[str, Any]:
    return read_json(MASTER_PATH)


def _load(vaga: Any) -> dict[str, Any]:
    """Accept a job dict or the slug of a saved job."""
    if isinstance(vaga, str):
        path = job_path(vaga)
        if not path.exists():
            raise ValueError(f"vaga não encontrada em data/jobs: {vaga}")
        return load_job(vaga)
    if not isinstance(vaga, dict):
        raise ValueError("vaga deve ser o objeto da adaptação ou o slug de uma vaga salva")
    return vaga


# --- adaptations --------------------------------------------------------------

def validate(vaga: Any) -> dict[str, Any]:
    job = _load(vaga)
    return validate_adaptation(job, _master())


def save(vaga: dict[str, Any], sobrescrever: bool = False) -> dict[str, Any]:
    job = dict(vaga)
    metadata = job.get("metadata", {})
    job["id"] = slugify(job.get("id") or f"{metadata.get('company_name', '')}-{metadata.get('role_title', '')}")
    job["schema_version"] = SCHEMA_VERSION
    job.setdefault("metadata", {}).setdefault("source_files", ["master_resume.json"])

    result = validate_adaptation(job, _master())
    if not result["ok"]:
        return {"salvo": False, **result}
    path = job_path(job["id"])
    if path.exists() and not sobrescrever:
        return {"salvo": False, "ok": True, "erros": [f"já existe data/jobs/{path.name}; use sobrescrever=true "
                                                       "para substituir"], "avisos": result["avisos"]}
    write_json(path, job)
    return {"salvo": True, "slug": job["id"], "arquivo": f"data/jobs/{path.name}", **result}


def render_pdfs(slug: str, idiomas: Optional[list[str]] = None, incluir_carta: bool = True) -> dict[str, Any]:
    job = _load(slug)
    result = validate_adaptation(job, _master())
    if not result["ok"]:
        return {"gerado": False, **result}

    from utils import AdaptedResume, JobMaterials, convert_html_to_pdf, render_html_cover_letter, render_html_resume

    destination = EXPORTS_DIR / job["id"]
    destination.mkdir(parents=True, exist_ok=True)
    files = []
    for lang in idiomas or list(LANGUAGES):
        if lang not in LANGUAGES:
            raise ValueError(f"idioma inválido: {lang}")
        resume = AdaptedResume(**job["resume"][lang])
        target = destination / f"curriculo_{lang}.pdf"
        target.write_bytes(convert_html_to_pdf(render_html_resume(resume, target_lang=lang, template_path=str(TEMPLATE))))
        files.append(target)
        if incluir_carta:
            letter = JobMaterials(**job["materials"][lang]).cover_letter
            target = destination / f"carta_{lang}.pdf"
            target.write_bytes(convert_html_to_pdf(render_html_cover_letter(letter)))
            files.append(target)
    return {"gerado": True, "arquivos": [str(f) for f in files], "avisos": result["avisos"]}


# --- applications -------------------------------------------------------------

def _read_applications() -> list[dict[str, Any]]:
    return read_json(tracking.APPLICATIONS_PATH)


def register(slug: Optional[str] = None, empresa: str = "", cargo: str = "", url: str = "",
             data: Optional[str] = None, notas: str = "") -> dict[str, Any]:
    applied = data or datetime.date.today().isoformat()
    datetime.date.fromisoformat(applied)
    if slug:
        job = _load(slug)
    else:
        if not empresa or not cargo:
            raise ValueError("informe o slug de uma vaga salva, ou empresa e cargo")
        job = {"id": slugify(f"{empresa}-{cargo}"),
               "metadata": {"company_name": empresa, "role_title": cargo, "url": url}}

    metadata = job.get("metadata", {})
    applications = _read_applications()
    existing_id = find_duplicate(url=metadata.get("url", ""), company=metadata.get("company_name", ""),
                                 role=metadata.get("role_title", ""), existing_jobs=[],
                                 existing_applications=applications)
    if existing_id:
        bare = existing_id.split("application:", 1)[-1]
        existing = next((a for a in applications if a.get("source_job_id") == existing_id or a.get("id") == bare), None)
        if existing:
            return {"registrado": False, "motivo": "candidatura já registrada",
                    "candidatura": {k: existing.get(k) for k in ("id", "company", "role", "status", "date_applied")}}

    meta = {"notes": notas} if notas else {}
    entry = tracking.register_application(job, applied, meta, history_source="mcp")
    return {"registrado": True, "candidatura": {k: entry.get(k) for k in ("id", "company", "role", "status", "date_applied", "url")}}


def update_status(candidatura_id: str, status: str, data: Optional[str] = None, nota: str = "",
                  etapa_atual: Optional[str] = None) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"status inválido: {status}. Use um de: {STATUSES}")
    when = data or datetime.date.today().isoformat()
    datetime.date.fromisoformat(when)
    applications = _read_applications()
    app = next((a for a in applications if str(a.get("id")) == str(candidatura_id)), None)
    if app is None:
        raise ValueError(f"candidatura não encontrada: {candidatura_id}")

    before = app.get("status")
    set_status(app, status, date=when, source="mcp", note=nota)
    if etapa_atual:
        app["current_stage"] = etapa_atual
    if status == "Rejeitado" and not app.get("date_rejected"):
        app["date_rejected"] = when
    if nota:
        app["notes"] = f"{app.get('notes', '')} | [{when}] {nota}".strip(" |")
    tracking._write_applications(applications)
    return {"id": app["id"], "empresa": app.get("company"), "status_anterior": before, "status": app["status"],
            "historico": app["status_history"]}
