"""
ETAPA 3 — Adapter: transforma o context_pack (recuperado SO do grafo)
em um blob de prompt para o LLM escrever o AdaptedResume.

Principios (definidos pelo usuario):
- So o grafo. Nada de master_resume, nada de recuperacao hibrida.
- O LLM recebe APENAS as evidencias que o grafo recuperou + os gaps honestos.
- Model-agnostico: recebe um `llm_callable(prompt) -> str` injetado.
- Schema de saida = o mesmo do artifact atual (AdaptedResume / JobMaterials),
  para comparacao justa com o metodo (A) dump-do-master.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parents[1]

SCHEMA_HINT = """\
Saida OBRIGATORIA em JSON, sem markdown, com esta estrutura:
{
  "resume": {
    "name": str, "title": str,
    "summary": str,                      # 2-3 frases, sob o ponto de vista do candidato
    "experience": [ { "company": str, "role": str, "dates": str,
                     "highlights": [ str (3-5 bullets) ] } ],
    "skills": [ str ],                   # so skills que constam no grafo recuperado
    "education": [ str ]
  },
  "materials": {
    "cover_letter": str,                 # dirigida a {company}, menciona a empresa
    "form_responses": [ { "question": str, "answer": str } ]
  },
  "metadata": {
    "fit_score": int (0-100),
    "good_points": [ str ],
    "improvement_points": [ str ],       # incluir os GAPS do grafo de forma honesta
    "language": "pt" | "en"
  }
}
REGRAS: use SOMENTE as evidencias fornecidas. Nao invente empresas, cargos, metricas
ou skills que nao estejam no contexto. Para os GAPS, seja explicito e honesto.
"""


def _company_block(pack: dict) -> str:
    lines = []
    for c in pack.get("companies", []):
        name = c["name"]["en"]
        loc = (c.get("location") or {}).get("en", "")
        dates = (c.get("dates") or {}).get("en", "")
        lines.append(f"- {name} ({loc}, {dates})")
        for r in c.get("roles", []):
            lines.append(f"    * {r['title']['en']} — {r.get('dates', {}).get('en', '')}")
    return "\n".join(lines)


def _evidence_block(pack: dict) -> str:
    lines = []
    for req in pack.get("per_requirement", []):
        lines.append(f"\n### Requisito: {req['requirement_text']}")
        for sk in req["skills"]:
            lines.append(f"  Skill relevante: {sk['label_en']} (evidencias no grafo: {sk['evidence_count']})")
            for b in sk.get("bullets", []):
                if not b.get("en"):
                    continue
                src = b.get("source", "")
                lines.append(f"    • {b['en']}   [source: {src}]")
    return "\n".join(lines)


def _metrics_block(pack: dict) -> str:
    lines = []
    for m in pack.get("metrics", []):
        lines.append(f"- {m.get('company')}: {m.get('value')} — {m.get('name_en')} ({m.get('context_en','')[:80]})")
    return "\n".join(lines)


def _gaps_block(pack: dict) -> str:
    if not pack.get("gaps"):
        return "(nenhum gap identificado no grafo)"
    return "\n".join(f"- {g['term']}  [{g['kind']}]" for g in pack["gaps"])


def build_adaptation_context(pack_path: str | Path) -> str:
    """Monta o prompt de adaptacao a partir do context_pack (so o grafo)."""
    pack = json.loads(Path(pack_path).read_text(encoding="utf-8"))
    company = pack["company"]
    title = pack["title"]

    prompt = f"""\
Voce e um redator de curriculo. Adapte o perfil abaixo para a vaga:

VAGA: {title} @ {company}

INSTRUCAO CRITICA: o contexto abaixo foi recuperado EXCLUSIVAMENTE de um grafo de
conhecimento construido a partir do curriculo mestre. NAO use nenhuma informacao externa.
Se o grafo nao tem evidencia de algo, diga que e gap — nao invente.

===== CANDIDATO =====
{pack['candidate']['name']}

===== EMPRESAS / CARGOS (do grafo) =====
{_company_block(pack)}

===== EVIDENCIAS RECUPERADAS POR REQUISITO (bullets reais do grafo) =====
{_evidence_block(pack)}

===== METRICAS (do grafo) =====
{_metrics_block(pack)}

===== GAPS HONESTOS (termos da vaga sem no de skill no grafo) =====
{_gaps_block(pack)}

===== SCHEMA DE SAIDA =====
{SCHEMA_HINT}
"""
    return prompt


def adapt_from_graph(
    pack_path: str | Path,
    llm_callable: Callable[[str], str],
    lang: str = "en",
    save_path: Optional[str | Path] = None,
) -> dict:
    """Orquestra: monta prompt do grafo -> chama LLM injetado -> devolve dict.

    llm_callable: funcao(prompt:str) -> str (JSON). Nao acoplado a nenhum provider.
    """
    prompt = build_adaptation_context(pack_path)
    # injeta idioma no prompt
    prompt += f"\nIDIOMA DA RESPOSTA: {lang}\n"
    raw = llm_callable(prompt)
    # tenta parsear JSON (o LLM pode envelopar em markdown)
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lower().startswith("json"):
            text = text[4:]
    data = json.loads(text)
    if save_path:
        Path(save_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


if __name__ == "__main__":
    # Teste sem LLM: so monta o prompt e imprime tamanho + amostra
    p = build_adaptation_context(ROOT / "data" / "jobs" / "sandboxaq-context-pack.json")
    print(f"Prompt montado: {len(p)} chars")
    print("--- amostra (cabecalho) ---")
    print("\n".join(p.splitlines()[:18]))
