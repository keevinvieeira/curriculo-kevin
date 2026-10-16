# Artefato de vaga v2 — mapa de evidências

`data/jobs/<slug>.json` com `"schema_version": 2`. É o formato v1 (ver README, Passo D)
mais um **mapa de evidências** em `evidence`: cada requisito da vaga aponta para os IDs
do `master_resume.json` que o comprovam, e o que não é comprovado vira gap explícito.

Artefatos sem `schema_version` são v1 e continuam válidos. `create_from_active` e o
radar (`engine/automation/ingestion.py`) já criam v2 com listas vazias.

## Estrutura

```json
{
  "id": "<slug>",
  "schema_version": 2,
  "metadata": { "...": "igual ao v1" },
  "triage":   { "...": "igual ao v1" },
  "resume":    { "pt": {}, "en": {} },
  "materials": { "pt": {}, "en": {} },
  "evidence": {
    "skills": { "pt": [], "en": [] },
    "requirements": [
      {
        "id": "req-01",
        "text": "Requisito como está na vaga",
        "priority": "must_have | nice_to_have",
        "knockout": true,
        "status": "covered | partial | gap",
        "evidence_ids": ["wipro-b05", "lang-english"],
        "note": "opcional — por que essas evidências comprovam"
      }
    ],
    "gaps": [
      {
        "requirement_id": "req-01",
        "severity": "blocker | high | medium | low",
        "detail": "o que falta",
        "mitigation": "como tratar sem inventar"
      }
    ]
  }
}
```

Exemplo completo e válido: [`examples/wellhub-evidence-map.json`](examples/wellhub-evidence-map.json).

## Regras (checadas por `job_store.validate_evidence_map`)

| Regra | Por quê |
|---|---|
| `requirements[].id` único; `text`, `priority`, `status` obrigatórios | referência estável dentro do artefato |
| `covered`/`partial` exigem ≥ 1 `evidence_ids` | nada é "coberto" sem prova |
| `gap` não pode citar `evidence_ids` | gap é gap |
| todo `partial`/`gap` tem entrada em `gaps` | a lacuna fica explícita, com mitigação |
| todo `evidence_id` existe no master (`resume_ids.build_index`) | zero alucinação, checável por máquina |
| `gaps[].requirement_id` aponta para um requisito; `severity` no enum | consistência |

`knockout`, `note`, `detail` e `mitigation` são opcionais.

## IDs citáveis do master

| Tipo | Formato | Exemplo |
|---|---|---|
| bullet | `<contêiner>-bNN` | `meu-barzin-b07`, `wipro-b05` |
| responsabilidade de cargo | `<contêiner>-rNN` (+ `same_as` → bullet) | `ai-career-os-r04` |
| cargo | `<empresa>-role-NN` | `wipro-role-01` |
| experiência / projeto | `exp-<slug>` / `proj-<slug>` | `exp-wipro`, `proj-meu-barzin` |
| idioma | `lang-<slug>` (mesmo ID em pt e en) | `lang-english` |
| formação / certificação / voluntariado | `edu-` / `cert-` / `vol-` | `edu-ufpr-filosofia` |

Prefira o ID mais específico (bullet > cargo > experiência). Os IDs nunca são
renumerados: depois de adicionar um item ao master, rode
`python -m scripts.assign_master_ids` para dar ID só ao que está sem.
