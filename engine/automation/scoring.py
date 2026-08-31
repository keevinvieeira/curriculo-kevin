"""Deterministic fit_score for the automation radar.

The rest of the Career OS (JobPipeline, validate_job, the Streamlit app) treats
`metadata.fit_score` as an opaque 0-100 int that a human (or an LLM session
following AGENTS.md) already decided. Nothing in the codebase computes it — see
`JobPipeline.process_job_artifact`'s `metadata.setdefault("fit_score", 95)`, and the
project's own IMPLEMENTATION_PLAN.md, which calls the current approach an "LLM guess".

This module is the one place that computes a fit_score for automation-discovered
jobs, on purpose *not* using an LLM for this primary gate: it's cheap, fast, fully
deterministic, and easy to unit test and tune. Callers (radar.py / workflow.py) must
always set `metadata["fit_score"]` explicitly from this before handing a job to
JobPipeline — never rely on the pipeline's own default.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Categorias-alvo (da sprint original) e suas palavras-chave PT/EN.
# Ajustar esta lista é a forma normal de recalibrar o radar — não precisa mexer
# na lógica de score abaixo.
# ---------------------------------------------------------------------------
PRIORITY_CATEGORIES: Dict[str, List[str]] = {
    "Product Marketing": ["product marketing", "marketing de produto", "pmm", "gtm messaging", "positioning"],
    "Growth": ["growth", "crescimento", "aquisição", "acquisition", "retention", "retenção"],
    "GTM": ["go-to-market", "go to market", "gtm strategy", "estratégia de gtm", "launch strategy"],
    "Product Strategy": ["product strategy", "estratégia de produto", "product vision", "roadmap"],
    "Product Ops": ["product operations", "product ops", "operações de produto", "process optimization"],
    "AI GTM": ["ai go-to-market", "ai gtm", "gtm de ia", "genai launch"],
    "AI Operations": ["ai operations", "ai ops", "operações de ia", "llm ops", "mlops"],
    "AI Policy": ["ai policy", "política de ia", "regulação de ia", "ai regulation"],
    "AI Ethics": ["ai ethics", "ética em ia", "responsible ai practices"],
    "Responsible AI": ["responsible ai", "ia responsável"],
    "Governance": ["ai governance", "governança de ia", "model governance", "data governance"],
    "Trust & Safety": ["trust and safety", "trust & safety", "confiança e segurança", "content moderation"],
    "Model Behavior": ["model behavior", "comportamento de modelo", "model alignment", "alinhamento de modelo"],
    "AI Evaluation": ["ai evaluation", "avaliação de ia", "model evaluation", "red teaming", "eval harness"],
}

# Frases que descartam a vaga de cara, independente do score numérico.
HARD_BLOCKER_PHRASES: List[str] = [
    "unpaid internship",
    "estágio não remunerado",
    "us citizens only",
    "us citizenship required",
    "apenas para cidadãos americanos",
    "security clearance required",
    "must be authorized to work in the us without sponsorship",
]

_BRAZIL_HINTS = ["brazil", "brasil", "são paulo", "sao paulo", "rio de janeiro", "curitiba", "belo horizonte", "remoto", "latam", "latin america"]
_REMOTE_HINTS = ["remote", "remoto", "work from home", "home office", "distributed team"]

_WEIGHTS = {"category_match": 50, "location": 25, "salary": 15, "recency": 10}
assert sum(_WEIGHTS.values()) == 100


@dataclass
class ScoreResult:
    total: int
    breakdown: Dict[str, int]
    matched_categories: List[str] = field(default_factory=list)
    hard_blockers: List[str] = field(default_factory=list)

    @property
    def passes_gate(self) -> bool:
        """Fit >= 80 and no hard blocker — the only thing that may auto-proceed to adaptation."""
        return self.total >= 80 and not self.hard_blockers


def _text_blob(title: str, description: str) -> str:
    return f"{title}\n{description}".casefold()


def _score_category_match(blob: str) -> tuple[int, List[str]]:
    matched = [name for name, keywords in PRIORITY_CATEGORIES.items() if any(kw in blob for kw in keywords)]
    if not matched:
        return 0, []
    # 1 categoria já garante uma boa base; múltiplas categorias reforçam o score,
    # com retornos decrescentes para não deixar o teto trivial de bater.
    ratio = min(len(matched) / 3, 1.0)
    return round(_WEIGHTS["category_match"] * (0.6 + 0.4 * ratio)), matched


def _score_location(location: str, remote: Optional[bool], blob: str) -> int:
    location_cf = (location or "").casefold()
    is_brazil = any(hint in location_cf for hint in _BRAZIL_HINTS) or any(hint in blob for hint in _BRAZIL_HINTS)
    is_remote = bool(remote) or any(hint in location_cf for hint in _REMOTE_HINTS) or any(hint in blob for hint in _REMOTE_HINTS)
    if is_brazil:
        return _WEIGHTS["location"]
    if is_remote:
        return round(_WEIGHTS["location"] * 0.8)
    if not location:
        return round(_WEIGHTS["location"] * 0.4)  # desconhecido: nem penaliza nem beneficia forte
    return 0


def _parse_salary_numbers(salary_range: Optional[str]) -> List[float]:
    if not salary_range:
        return []
    # Aceita formatos como "R$ 15.000 - R$ 22.000", "$3,500 - $5,000 USD/mês", "120k-150k"
    cleaned = salary_range.replace(".", "").replace(",", "")
    numbers = re.findall(r"\d+(?:k)?", cleaned, flags=re.IGNORECASE)
    values = []
    for n in numbers:
        n = n.lower()
        if n.endswith("k"):
            values.append(float(n[:-1]) * 1000)
        else:
            values.append(float(n))
    return values


def _score_salary(salary_range: Optional[str], min_expected: Optional[float]) -> int:
    if not salary_range:
        return round(_WEIGHTS["salary"] * 0.6)  # sem info: nem bônus nem penalidade forte
    values = _parse_salary_numbers(salary_range)
    if not values:
        return round(_WEIGHTS["salary"] * 0.6)
    if min_expected is None:
        return _WEIGHTS["salary"]  # tem faixa, sem expectativa pra comparar: crédito total
    if max(values) >= min_expected:
        return _WEIGHTS["salary"]
    if max(values) >= min_expected * 0.85:
        return round(_WEIGHTS["salary"] * 0.5)
    return 0


def _score_recency(posted_at: Optional[str], now: Optional[datetime] = None) -> int:
    if not posted_at:
        return round(_WEIGHTS["recency"] * 0.7)  # desconhecido: crédito parcial
    try:
        posted = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
    except ValueError:
        return round(_WEIGHTS["recency"] * 0.7)
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    age_days = (reference - posted).days
    if age_days <= 14:
        return _WEIGHTS["recency"]
    if age_days <= 45:
        return round(_WEIGHTS["recency"] * 0.6)
    return 0


def score_job(
    *,
    title: str,
    description: str,
    location: str = "",
    remote: Optional[bool] = None,
    salary_range: Optional[str] = None,
    posted_at: Optional[str] = None,
    min_salary_expected: Optional[float] = None,
) -> ScoreResult:
    """Compute a deterministic 0-100 fit score plus a breakdown and any hard blockers.

    All inputs are plain strings/primitives (not the full data/jobs/<slug>.json shape)
    so this stays trivially unit-testable and reusable from radar.py before a job
    artifact even exists yet.
    """
    blob = _text_blob(title, description)
    blockers = [phrase for phrase in HARD_BLOCKER_PHRASES if phrase in blob]

    category_score, matched = _score_category_match(blob)
    location_score = _score_location(location, remote, blob)
    salary_score = _score_salary(salary_range, min_salary_expected)
    recency_score = _score_recency(posted_at)

    breakdown = {
        "category_match": category_score,
        "location": location_score,
        "salary": salary_score,
        "recency": recency_score,
    }
    total = sum(breakdown.values())
    return ScoreResult(total=total, breakdown=breakdown, matched_categories=matched, hard_blockers=blockers)
