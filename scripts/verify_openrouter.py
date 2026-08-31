"""
Verificação ponta-a-ponta da integração com a OpenRouter — o único passo do sprint de
automação que precisa de rede aberta para `openrouter.ai` e, por isso, não pôde ser
feito no ambiente onde este código foi escrito.

Roda três checagens, da mais barata para a mais cara:

  1. A chave está presente e o catálogo de modelos responde (nenhum token gasto).
  2. O modelo configurado existe no catálogo e declara suporte a `structured_outputs`.
  3. Uma chamada real, pequena, pelo mesmo caminho de código que o pipeline usa
     (`llm_client.generate_structured`), validando que a resposta volta como um modelo
     Pydantic preenchido — que é a garantia da qual todo o resto do projeto depende.

Uso:
    python scripts/verify_openrouter.py             # usa OPENROUTER_API_KEY do .env/ambiente
    python scripts/verify_openrouter.py --skip-call # só os passos 1 e 2, sem gastar tokens
    python scripts/verify_openrouter.py --model google/gemini-3.5-flash-lite
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests
from pydantic import BaseModel, Field

import llm_client

OK = "[OK]  "
FAIL = "[FALHOU] "
INFO = "[..]  "


class _SmokeTestAnswer(BaseModel):
    """Schema mínimo — o objetivo é provar que a saída estruturada funciona, não gerar conteúdo."""

    idioma: str = Field(description="O idioma em que esta resposta foi escrita, ex: 'português'")
    numero: int = Field(description="O número 7, exatamente")


def _check_key() -> str | None:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        print(f"{FAIL}OPENROUTER_API_KEY não encontrada no ambiente nem no .env.")
        print("       Defina-a antes de rodar (veja .env.example).")
        return None
    print(f"{OK}OPENROUTER_API_KEY encontrada (…{key[-6:]}).")
    return key


def _check_catalog(model: str) -> bool:
    print(f"{INFO}Consultando o catálogo de modelos da OpenRouter…")
    try:
        response = requests.get(f"{llm_client.resolve_base_url()}/models", timeout=30)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"{FAIL}Não foi possível alcançar a OpenRouter: {exc}")
        print("       (Rede bloqueada? Proxy corporativo? Tente `curl https://openrouter.ai/api/v1/models`.)")
        return False

    models = {item.get("id"): item for item in response.json().get("data", [])}
    print(f"{OK}Catálogo respondeu: {len(models)} modelos disponíveis.")

    entry = models.get(model)
    if entry is None:
        print(f"{FAIL}O modelo configurado '{model}' NÃO está no catálogo atual.")
        print("       Escolha outro em https://openrouter.ai/models e ajuste OPENROUTER_MODEL.")
        return False

    supported = entry.get("supported_parameters") or []
    if "structured_outputs" not in supported and "tools" not in supported:
        print(f"{FAIL}'{model}' existe, mas não declara structured_outputs/tools.")
        print("       Este projeto depende de saída estruturada — escolha outro modelo.")
        return False

    print(f"{OK}'{model}' existe e suporta saída estruturada.")
    return True


def _check_live_call(model: str, api_key: str) -> bool:
    print(f"{INFO}Fazendo uma chamada real pequena via llm_client.generate_structured…")
    try:
        result = llm_client.generate_structured(
            _SmokeTestAnswer,
            "Responda em português. Preencha o campo 'idioma' com o idioma da sua resposta "
            "e o campo 'numero' com o número 7.",
            temperature=0.0,
            api_key=api_key,
            model=model,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"{FAIL}A chamada falhou: {type(exc).__name__}: {exc}")
        return False

    if not isinstance(result, _SmokeTestAnswer):
        print(f"{FAIL}A resposta não voltou como modelo Pydantic válido: {result!r}")
        return False

    print(f"{OK}Resposta validada como Pydantic: idioma={result.idioma!r}, numero={result.numero}")
    if result.numero != 7:
        print("       (Aviso: o modelo não seguiu a instrução exata do número — a integração "
              "está funcionando, mas vale considerar um modelo mais aderente a instruções.)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Verifica a integração real com a OpenRouter.")
    parser.add_argument("--model", default=None, help="Modelo a testar (default: OPENROUTER_MODEL ou o padrão do projeto)")
    parser.add_argument("--skip-call", action="store_true", help="Não fazer a chamada real (não gasta tokens)")
    args = parser.parse_args()

    model = args.model or os.getenv("OPENROUTER_MODEL") or llm_client.DEFAULT_MODEL
    print(f"Modelo em teste: {model}")
    print(f"Endpoint: {llm_client.resolve_base_url()}\n")

    key = _check_key()
    if not key:
        sys.exit(1)

    if not _check_catalog(model):
        sys.exit(1)

    if args.skip_call:
        print("\n[--skip-call] Chamada real pulada. Catálogo e chave OK.")
        return

    if not _check_live_call(model, key):
        sys.exit(1)

    print("\nTudo certo: a migração Gemini -> OpenRouter está funcionando ponta a ponta.")


if __name__ == "__main__":
    main()
