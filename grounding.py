"""Grounding guardrail for adapted resumes (Fase 2).

Deterministic checks that an adaptation only rephrases facts from master_resume.json:

errors (block saving / PDF):
- every experience bullet is listed in evidence.bullet_sources with ≥1 master ID;
- every cited ID exists;
- every number in a bullet appears in the text of the IDs it cites;
- every number in the summary appears somewhere in the master;
- every company matches a master company or project;
- every role shares at least half its words with a master title of that company;
- the evidence map (requirements/gaps) is present and valid.

warnings (reported, never block):
- role words that are not in the master title (e.g. an added "Automação");
- skills and tool-like terms (Salesforce, n8n, SQL…) not found in the master text.

evidence.bullet_sources format, per language:
    [{"texto": "<bullet exactly as in resume>", "ids": ["wipro-b05", ...]}, ...]
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from job_store import LANGUAGES, validate_evidence_map, validate_job
from resume_ids import build_index

_NUMBER_RE = re.compile(r"(\d+(?:[.,]\d+)*)\s*([kK])?")
_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "de", "da", "do", "das", "dos", "e", "em", "para", "com", "a", "o", "as", "os", "the", "and", "of",
    "for", "in", "at", "on", "to", "projeto", "project",
}
# Words that look like tools/brands: internal capital (HubSpot), digits (n8n, GA4), or ALL-CAPS (SQL, CRM).
_TOOL_RE = re.compile(r"\b(?:[A-Za-z]*[a-z][A-Z][A-Za-z0-9]*|[A-Za-z]+\d[A-Za-z0-9]*|[A-Z]{2,}[A-Za-z0-9]*)\b")


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().casefold()


# Role-title words that mean the same in pt and en, so "Especialista" matches "Specialist".
_TITLE_SYNONYMS = {
    "especialista": "specialist", "consultor": "consultant", "consultora": "consultant",
    "gerente": "manager", "lider": "lead", "analista": "analyst", "coordenador": "coordinator",
    "fundador": "founder", "produto": "product", "produtos": "product", "projetos": "projects",
    "operacoes": "operations", "comunidades": "community", "comunidade": "community",
    "arquiteto": "architect", "sistemas": "systems", "assistente": "assistant",
    "administrativo": "administrative", "vendas": "sales", "ia": "ai", "responsavel": "lead",
}


def _words(text: str) -> set[str]:
    return set(_WORD_RE.findall(_fold(text))) - _STOPWORDS


def _title_words(text: str) -> set[str]:
    return {_TITLE_SYNONYMS.get(w, w) for w in _words(text)}


def _numbers(text: str) -> set[str]:
    """Digit strings with separators removed: '43,9%' -> '439', '10.000' -> '10000', '50k' -> '50000'."""
    found = set()
    for digits, thousands in _NUMBER_RE.findall(text or ""):
        plain = re.sub(r"\D", "", digits)
        found.add(plain)
        if thousands:
            found.add(plain + "000")
    return found


def _master_text(master: dict[str, Any]) -> str:
    return _fold(json.dumps(master, ensure_ascii=False))


def _master_titles(master: dict[str, Any]) -> dict[str, list[str]]:
    """company-ish name -> role titles (pt and en); projects share their company's titles."""
    titles: dict[str, list[str]] = {}
    for exp in master.get("work_experience", []):
        role_titles = [t for role in exp.get("roles", []) for t in (role.get("title") or {}).values()]
        names = [exp.get("company", "").split(" — ")[0], *(p.get("name", "") for p in exp.get("projects", []))]
        for name in names:
            titles[name] = role_titles
    return titles


def _match_company(company: str, known: list[str]) -> str | None:
    words = _words(re.sub(r"\(.*?\)", "", company))
    best, best_score = None, 0.0
    for name in known:
        candidate = _words(name)
        if not words or not candidate:
            continue
        score = len(words & candidate) / len(words)
        if score > best_score:
            best, best_score = name, score
    return best if best_score >= 0.5 else None


def validate_grounding(job: dict[str, Any], master: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    evidence = job.get("evidence", {})
    index = build_index(master)
    master_text = _master_text(master)
    master_numbers = _numbers(json.dumps(master, ensure_ascii=False))
    titles_by_company = _master_titles(master)

    if not evidence.get("requirements"):
        errors.append("evidence.requirements está vazio: mapeie os requisitos da vaga para IDs do master")
    errors.extend(validate_evidence_map(evidence, master))

    sources = evidence.get("bullet_sources", {})
    for lang in LANGUAGES:
        resume = job.get("resume", {}).get(lang)
        if not resume:
            continue
        by_text = {s.get("texto"): s.get("ids") or [] for s in sources.get(lang, [])}

        extra = _numbers(resume.get("summary", "")) - master_numbers
        if extra:
            errors.append(f"resume.{lang}.summary: números que não existem no master: {sorted(extra)}")

        for exp in resume.get("experience", []):
            company, role = exp.get("company", ""), exp.get("role", "")
            matched = _match_company(company, list(titles_by_company))
            if not matched:
                errors.append(f"resume.{lang}: empresa não encontrada no master: '{company}'")
            else:
                title_words = set().union(*(_title_words(t) for t in titles_by_company[matched])) if titles_by_company[matched] else set()
                role_words = _title_words(re.sub(r"\(.*?\)", "", role))
                if role_words and len(role_words & title_words) / len(role_words) < 0.5:
                    errors.append(f"resume.{lang}: cargo '{role}' não corresponde a nenhum cargo de '{matched}' no master")
                elif role_words - title_words:
                    warnings.append(f"resume.{lang}: cargo '{role}' tem termos fora do título do master: "
                                    f"{sorted(role_words - title_words)}")

            for bullet in exp.get("bullets", []):
                where = f"resume.{lang} [{company}] \"{bullet[:60]}…\""
                ids = by_text.get(bullet)
                if not ids:
                    errors.append(f"{where}: sem entrada em evidence.bullet_sources.{lang} com IDs")
                    continue
                unknown = [i for i in ids if i not in index]
                if unknown:
                    errors.append(f"{where}: IDs inexistentes no master: {unknown}")
                    continue
                source_text = " ".join(str(index[i].get(lang) or index[i].get("pt") or "") for i in ids)
                missing = _numbers(bullet) - _numbers(source_text)
                if missing:
                    errors.append(f"{where}: números ausentes nos IDs citados {ids}: {sorted(missing)}")

        unknown_skills = [s for cat in resume.get("skills", []) for s in cat.get("skills", [])
                          if _fold(s) not in master_text]
        if unknown_skills:
            warnings.append(f"resume.{lang}.skills: não aparecem literalmente no master: {unknown_skills}")

        text = " ".join([resume.get("summary", ""), *(b for e in resume.get("experience", []) for b in e.get("bullets", []))])
        odd_terms = sorted({t for t in _TOOL_RE.findall(text) if _fold(t) not in master_text})
        if odd_terms:
            warnings.append(f"resume.{lang}: termos com cara de ferramenta/sigla fora do master: {odd_terms}")

    return errors, warnings


def validate_adaptation(job: dict[str, Any], master: dict[str, Any]) -> dict[str, Any]:
    """validate_job (structure, v1 rules) + grounding. The single check the MCP write tools use."""
    from job_store import job_warnings

    errors = validate_job(job, master)
    grounding_errors, warnings = validate_grounding(job, master)
    errors += [e for e in grounding_errors if e not in errors]
    warnings = job_warnings(job) + warnings
    return {"ok": not errors, "erros": errors, "avisos": warnings}
