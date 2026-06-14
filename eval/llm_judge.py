"""
Model-graded judges para o Kirin Eval Harness.
Usa LLM (deepseek-chat) como juiz para avaliar a qualidade dos outputs dos agentes.

Diferente dos rules-based judges, estes usam o modelo para avaliar:
- Coerência semântica
- Qualidade da argumentação
- Adequação ao contexto
- Presença de alucinações
"""

import json
import logging
import os
import asyncio
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Configuração do LLM
LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:4000")
JUDGE_MODEL = os.getenv("KIRIN_JUDGE_MODEL", "deepseek-chat")
JUDGE_TIMEOUT = int(os.getenv("KIRIN_JUDGE_TIMEOUT", "60"))
JUDGE_MAX_RETRIES = int(os.getenv("KIRIN_JUDGE_MAX_RETRIES", "3"))
JUDGE_RETRY_DELAY = float(os.getenv("KIRIN_JUDGE_RETRY_DELAY", "1.0"))


@dataclass
class LLMJudgeResult:
    """Resultado de um judge model-graded via LLM."""
    score: int  # 0-100
    explanation: str
    criteria_scores: Dict[str, int]  # criteria_name → score (0-100)
    passed: bool
    raw_llm_response: str = ""

    def to_dict(self) -> Dict:
        return {
            "score": self.score,
            "explanation": self.explanation,
            "criteria_scores": self.criteria_scores,
            "passed": self.passed,
            "judge_type": "model-graded",
            "model": JUDGE_MODEL
        }


class LLMJudge:
    """
    Judge baseado em LLM para avaliar outputs dos agentes.
    
    Usa deepseek-chat como juiz para avaliar:
    1. Coerência do output com o contexto
    2. Qualidade da argumentação
    3. Presença de alucinações
    4. Adequação ao formato esperado
    """

    def __init__(self, model: str = JUDGE_MODEL):
        self.model = model
        self._client = None

    async def _get_client(self):
        """Obtém cliente HTTP para chamar o LLM."""
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def _call_llm(self, prompt: str) -> str:
        """Chama o LLM com retry logic e retorna a resposta."""
        client = await self._get_client()

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Você é um juiz especializado em avaliar a qualidade de outputs de agentes de IA para prospecção B2B. Avalie de forma objetiva e retorne APENAS um JSON válido."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,  # Baixa temperatura para consistência
            "max_tokens": 1000
        }

        last_error = None
        for attempt in range(JUDGE_MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    client.post(
                        f"{LITELLM_URL}/v1/chat/completions",
                        json=payload
                    ),
                    timeout=JUDGE_TIMEOUT
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except asyncio.TimeoutError:
                last_error = f"Timeout após {JUDGE_TIMEOUT}s (tentativa {attempt + 1}/{JUDGE_MAX_RETRIES})"
                logger.warning(f"LLM judge timeout: {last_error}")
            except Exception as e:
                last_error = f"{e} (tentativa {attempt + 1}/{JUDGE_MAX_RETRIES})"
                logger.warning(f"LLM judge error: {last_error}")

            # Esperar antes de retry (exponential backoff)
            if attempt < JUDGE_MAX_RETRIES - 1:
                delay = JUDGE_RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)

        logger.error(f"LLM judge falhou após {JUDGE_MAX_RETRIES} tentativas: {last_error}")
        return ""

    def _build_enricher_prompt(self, output: Dict, context: Dict) -> str:
        """Constrói prompt para avaliar Enricher."""
        lead = context.get("lead", {})
        dossier = output.get("dossie", {})

        return f"""Avalie a qualidade do dossiê gerado para o lead.

LEAD:
- Nome: {lead.get('name', 'N/A')}
- Endereço: {lead.get('address', 'N/A')}
- Telefone: {lead.get('phone', 'N/A')}

DOSSIÊ GERADO:
{json.dumps(dossier, indent=2, ensure_ascii=False)}

CRITÉRIOS DE AVALIAÇÃO:
1. Estrutura JSON (0-100): Todos os campos obrigatórios presentes?
2. Especificidade (0-100): O resumo menciona detalhes específicos do lead?
3. Pontos fracos acionáveis (0-100): São específicos e não genéricos?
4. Maturidade digital (0-100): É coerente com os dados fornecidos?
5. Sem alucinações (0-100): Não inventa dados não fornecidos?
6. Tool calls (0-100): Ordem correta (complete → store)?

Retorne APENAS um JSON:
{{
    "score": <0-100>,
    "explanation": "<explicação objetiva>",
    "criteria": {{
        "json_structure": <0-100>,
        "specificity": <0-100>,
        "actionable_weaknesses": <0-100>,
        "maturity_coherence": <0-100>,
        "no_hallucination": <0-100>,
        "tool_order": <0-100>
    }}
}}"""

    def _build_scorer_prompt(self, output: Dict, context: Dict) -> str:
        """Constrói prompt para avaliar Scorer."""
        dossier = context.get("dossier", {})

        return f"""Avalie a calibração do score atribuído ao lead.

OUTPUT DO SCORER:
{json.dumps(output, indent=2, ensure_ascii=False)}

DOSSIÊ DO LEAD:
{json.dumps(dossier, indent=2, ensure_ascii=False)}

CRITÉRIOS DE AVALIAÇÃO:
1. Score no range válido (0-100): Está entre 0-100?
2. Faixa coerente (0-100): "frio" ≤39, "morno" 40-69, "quente" ≥70?
3. Justificativa (0-100): Tem 3-5 frases, é específica?
4. Coerência com dossier (0-100): Score altojustifica com pontos fortes?
5. JSON válido (0-100): Campos score, faixa, justificativa presentes?

Retorne APENAS um JSON:
{{
    "score": <0-100>,
    "explanation": "<explicação objetiva>",
    "criteria": {{
        "score_range": <0-100>,
        "faixa_coherence": <0-100>,
        "justification_quality": <0-100>,
        "dossier_coherence": <0-100>,
        "json_valid": <0-100>
    }}
}}"""

    def _build_messenger_prompt(self, output: Dict, context: Dict) -> str:
        """Constrói prompt para avaliar Messenger."""
        lead = context.get("lead", {})
        dossier = context.get("dossier", {})

        return f"""Avalie a qualidade da mensagem WhatsApp gerada.

MENSAGEM:
{output.get('message', 'N/A')}

LEAD:
- Nome: {lead.get('name', 'N/A')}

DOSSIÊ:
- Pontos fracos: {dossier.get('pontos_fracos', [])}
- Oportunidades: {dossier.get('oportunidades', [])}

CRITÉRIOS DE AVALIAÇÃO:
1. Limite de 300 chars (0-100): Respeita o limite?
2. Menciona negócio (0-100): Nome do lead aparece na mensagem?
3. Personalização (0-100): Referencia pontos do dossiê?
4. Opt-out (0-100): Inclui instrução "SAIR"?
5. Tom (0-100): Profissional, não agressivo?
6. Português (0-100): Está em PT-BR?

Retorne APENAS um JSON:
{{
    "score": <0-100>,
    "explanation": "<explicação objetiva>",
    "criteria": {{
        "length_limit": <0-100>,
        "mentions_business": <0-100>,
        "personalization": <0-100>,
        "opt_out": <0-100>,
        "tone": <0-100>,
        "portuguese": <0-100>
    }}
}}"""

    def _build_researcher_prompt(self, output: Dict, context: Dict) -> str:
        """Constrói prompt para avaliar Researcher."""
        return f"""Avalie a qualidade da pesquisa realizada.

OUTPUT DO PESQUISADOR:
{json.dumps(output, indent=2, ensure_ascii=False)}

CRITÉRIOS DE AVALIAÇÃO:
1. Fontes presentes (0-100): Pelo menos 2 fontes?
2. Fontes válidas (0-100): URLs reais e acessíveis?
3. Relevância (0-100): Fontes relevantes para o lead?
4. JSON estruturado (0-100): Campos fontes_consultadas e pesquisa?

Retorne APENAS um JSON:
{{
    "score": <0-100>,
    "explanation": "<explicação objetiva>",
    "criteria": {{
        "sources_present": <0-100>,
        "valid_sources": <0-100>,
        "relevance": <0-100>,
        "json_structure": <0-100>
    }}
}}"""

    def _parse_llm_response(self, response: str) -> Optional[Dict]:
        """Parse da resposta do LLM, extraindo JSON."""
        try:
            # Tentar extrair JSON da resposta
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass
        return None

    async def judge_enricher(self, output: Dict, context: Dict) -> LLMJudgeResult:
        """Avalia Enricher usando LLM."""
        prompt = self._build_enricher_prompt(output, context)
        raw_response = await self._call_llm(prompt)

        parsed = self._parse_llm_response(raw_response)
        if not parsed:
            return LLMJudgeResult(
                score=50,
                explanation="Falha ao parsear resposta do LLM judge",
                criteria_scores={},
                passed=False,
                raw_llm_response=raw_response
            )

        score = parsed.get("score", 50)
        return LLMJudgeResult(
            score=score,
            explanation=parsed.get("explanation", ""),
            criteria_scores=parsed.get("criteria", {}),
            passed=score >= 80,
            raw_llm_response=raw_response
        )

    async def judge_scorer(self, output: Dict, context: Dict) -> LLMJudgeResult:
        """Avalia Scorer usando LLM."""
        prompt = self._build_scorer_prompt(output, context)
        raw_response = await self._call_llm(prompt)

        parsed = self._parse_llm_response(raw_response)
        if not parsed:
            return LLMJudgeResult(
                score=50,
                explanation="Falha ao parsear resposta do LLM judge",
                criteria_scores={},
                passed=False,
                raw_llm_response=raw_response
            )

        score = parsed.get("score", 50)
        return LLMJudgeResult(
            score=score,
            explanation=parsed.get("explanation", ""),
            criteria_scores=parsed.get("criteria", {}),
            passed=score >= 80,
            raw_llm_response=raw_response
        )

    async def judge_messenger(self, output: Dict, context: Dict) -> LLMJudgeResult:
        """Avalia Messenger usando LLM."""
        prompt = self._build_messenger_prompt(output, context)
        raw_response = await self._call_llm(prompt)

        parsed = self._parse_llm_response(raw_response)
        if not parsed:
            return LLMJudgeResult(
                score=50,
                explanation="Falha ao parsear resposta do LLM judge",
                criteria_scores={},
                passed=False,
                raw_llm_response=raw_response
            )

        score = parsed.get("score", 50)
        return LLMJudgeResult(
            score=score,
            explanation=parsed.get("explanation", ""),
            criteria_scores=parsed.get("criteria", {}),
            passed=score >= 80,
            raw_llm_response=raw_response
        )

    async def judge_researcher(self, output: Dict, context: Dict) -> LLMJudgeResult:
        """Avalia Researcher usando LLM."""
        prompt = self._build_researcher_prompt(output, context)
        raw_response = await self._call_llm(prompt)

        parsed = self._parse_llm_response(raw_response)
        if not parsed:
            return LLMJudgeResult(
                score=50,
                explanation="Falha ao parsear resposta do LLM judge",
                criteria_scores={},
                passed=False,
                raw_llm_response=raw_response
            )

        score = parsed.get("score", 50)
        return LLMJudgeResult(
            score=score,
            explanation=parsed.get("explanation", ""),
            criteria_scores=parsed.get("criteria", {}),
            passed=score >= 80,
            raw_llm_response=raw_response
        )

    async def judge(self, agent_name: str, output: Dict, context: Dict) -> LLMJudgeResult:
        """Judge genérico que despacha para o judge específico."""
        judges = {
            "enricher": self.judge_enricher,
            "scorer": self.judge_scorer,
            "messenger": self.judge_messenger,
            "researcher": self.judge_researcher,
        }

        judge_fn = judges.get(agent_name)
        if judge_fn:
            return await judge_fn(output, context)

        # Judge genérico para agentes não implementados
        return LLMJudgeResult(
            score=50,
            explanation=f"Judge model-graded não implementado para {agent_name}",
            criteria_scores={"generic": 50},
            passed=False
        )

    async def close(self):
        """Fecha o cliente HTTP."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Instância global
_llm_judge: Optional[LLMJudge] = None


def get_llm_judge() -> LLMJudge:
    """Retorna instância singleton do LLMJudge."""
    global _llm_judge
    if _llm_judge is None:
        _llm_judge = LLMJudge()
    return _llm_judge
