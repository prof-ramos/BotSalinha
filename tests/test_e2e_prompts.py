"""
BotSalinha — Teste E2E: Config YAML + Prompts + API OpenAI

Testa cada versão de prompt (v1, v2, v3) com uma pergunta real
contra a API da OpenAI (gpt-4o-mini), validando o fluxo completo:
  config.yaml → yaml_config → AgentWrapper → OpenAI API → resposta

Inclui delay entre chamadas para respeitar rate limits.
"""

import asyncio
import sys
import time
from pathlib import Path

import pytest

# Garantir que o projeto está no path (adiciona diretório raiz do projeto)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

# Delay entre chamadas para respeitar rate limits (segundos)
# OpenAI tem limites mais generosos que o Gemini free tier
DELAY_BETWEEN_CALLS = 5


async def prompt_e2e(prompt_file: str, question: str) -> dict:
    """Testa um prompt específico com a API real da OpenAI.

    Args:
        prompt_file: Nome do arquivo de prompt (ex: prompt_v1.md)
        question: Pergunta a ser enviada ao modelo

    Returns:
        Dict com resultados do teste
    """
    from agno.agent import Agent
    from agno.models.openai import OpenAIChat

    from src.config.yaml_config import AgentBehaviorConfig, ModelConfig, PromptConfig, YamlConfig

    # Carregar config com o prompt específico
    config = YamlConfig(
        model=ModelConfig(provider="openai", id="gpt-4o-mini", temperature=0.3),
        prompt=PromptConfig(file=prompt_file),
        agent=AgentBehaviorConfig(markdown=True, add_datetime=True, debug_mode=False),
    )

    prompt_content = config.prompt_content
    model_id = config.model.model_id

    print(f"\n{'=' * 60}")
    print(f"📄 Prompt: {prompt_file}")
    print(f"🤖 Modelo: {model_id}")
    print(f"📏 Tamanho do prompt de sistema: {len(prompt_content)} chars")
    print(f"❓ Pergunta: {question}")
    print(f"{'=' * 60}")

    # Criar agente com o modelo OpenAI
    agent = Agent(
        name="BotSalinha",
        model=OpenAIChat(id=model_id),
        instructions=prompt_content,
        add_datetime_to_context=config.agent.add_datetime,
        markdown=config.agent.markdown,
        debug_mode=config.agent.debug_mode,
    )

    # Chamar a API real
    start_time = time.time()
    try:
        response = await asyncio.wait_for(agent.arun(question), timeout=30.0)
        elapsed = time.time() - start_time

        if response and response.content:
            content = response.content

            # Verificar se a resposta é realmente conteúdo (não erro HTTP)
            if "429" in content and "Too Many Requests" in content:
                print(f"\n⚠️  Rate limit atingido ({elapsed:.2f}s)")
                return {
                    "prompt": prompt_file,
                    "status": "RATE_LIMITED",
                    "time_s": round(elapsed, 2),
                    "response_chars": 0,
                }

            print(f"\n✅ Resposta recebida ({elapsed:.2f}s, {len(content)} chars)")
            print(f"{'─' * 60}")
            # Mostrar primeiros 500 chars
            preview = content[:500]
            if len(content) > 500:
                preview += f"\n... (+ {len(content) - 500} chars)"
            print(preview)
            print(f"{'─' * 60}")

            # Validações de conteúdo
            checks = {
                "resposta_em_portugues": any(
                    w in content.lower()
                    for w in ["direito", "lei", "princípio", "administração", "legal"]
                ),
                "nao_vazia": len(content) > 50,
                "sem_erro_api": "error" not in content.lower()[:50],
            }
            all_checks = all(checks.values())
            for check, passed in checks.items():
                print(f"  {'✅' if passed else '❌'} {check}")

            return {
                "prompt": prompt_file,
                "status": "OK" if all_checks else "CONTENT_ISSUE",
                "time_s": round(elapsed, 2),
                "response_chars": len(content),
            }
        else:
            print(f"\n❌ Resposta vazia ({elapsed:.2f}s)")
            return {
                "prompt": prompt_file,
                "status": "EMPTY_RESPONSE",
                "time_s": round(elapsed, 2),
                "response_chars": 0,
            }
    except TimeoutError:
        elapsed = time.time() - start_time
        print("\n⏱️  Timeout após 30s")
        return {
            "prompt": prompt_file,
            "status": "TIMEOUT",
            "time_s": round(elapsed, 2),
            "response_chars": 0,
        }
    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = str(e)
        if "429" in error_msg or "rate_limit" in error_msg.lower():
            print(f"\n⚠️  Rate limit: {elapsed:.2f}s")
            return {
                "prompt": prompt_file,
                "status": "RATE_LIMITED",
                "time_s": round(elapsed, 2),
                "response_chars": 0,
            }
        print(f"\n❌ Erro: {type(e).__name__}: {e} ({elapsed:.2f}s)")
        return {
            "prompt": prompt_file,
            "status": f"ERROR: {type(e).__name__}",
            "time_s": round(elapsed, 2),
            "response_chars": 0,
        }


async def main() -> int:
    """Executa testes E2E com os 3 prompts."""
    print("🚀 BotSalinha — Teste E2E: Config YAML + Prompts + OpenAI API")
    print("=" * 60)

    # Pergunta de teste que exercita conhecimento jurídico
    question = "Explique o princípio da legalidade no Direito Administrativo brasileiro."

    prompts = ["prompt_v1.md", "prompt_v2.json", "prompt_v3.md"]
    results = []

    for i, prompt_file in enumerate(prompts):
        if i > 0:
            print(f"\n⏳ Aguardando {DELAY_BETWEEN_CALLS}s antes do próximo teste (rate limit)...")
            await asyncio.sleep(DELAY_BETWEEN_CALLS)

        result = await prompt_e2e(prompt_file, question)
        results.append(result)

    # Resumo
    print(f"\n\n{'=' * 60}")
    print("📊 RESUMO DOS TESTES E2E")
    print(f"{'=' * 60}")
    print(f"{'Prompt':<20} {'Status':<20} {'Tempo':<10} {'Chars':<10}")
    print(f"{'─' * 20} {'─' * 20} {'─' * 10} {'─' * 10}")
    for r in results:
        print(f"{r['prompt']:<20} {r['status']:<20} {r['time_s']:<10} {r['response_chars']:<10}")

    # Verificar se todos passaram
    ok_count = sum(1 for r in results if r["status"] == "OK")
    rate_limited = sum(1 for r in results if r["status"] == "RATE_LIMITED")
    failed = sum(1 for r in results if r["status"] not in ("OK", "RATE_LIMITED"))

    print(f"\n✅ Passaram: {ok_count}/{len(results)}")
    if rate_limited:
        print(f"⚠️  Rate limited: {rate_limited}/{len(results)} (quota esgotada)")
    if failed:
        print(f"❌ Falharam: {failed}/{len(results)}")

    return 0 if ok_count == len(results) else (2 if rate_limited and failed == 0 else 1)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


@pytest.mark.e2e
@pytest.mark.ai_provider
@pytest.mark.asyncio
async def test_e2e_prompts():
    """
    Pytest wrapper for E2E prompt tests.

    This test runs the same logic as the standalone main() function
    but in a pytest-compatible format.

    Exit codes:
    - 0: All tests passed
    - 2: Rate limit/quota exceeded (skip test)
    - Other: Failure
    """
    import pytest as pytest_module

    result = await main()
    if result == 2:
        pytest_module.skip("Rate limit/quota exceeded")
    assert result == 0, f"E2E prompts failed with code {result}"
