"""
PROSPECTUS-KERNEL EVAL — Framework de Avaliação Abductiva
Baseado em Augusto Galego (Groomy, Harness, Evals) + Abdução Sistêmica
"""

from .prospectus_kernel_eval_harness import (
    ProspectusKernelEvalHarness,
    SkepticAgent,
    JudgeFactory,
    Dimension,
    SkepticReport,
    JudgeResult,
    DimensionResult,
    EvalReport
)

from .llm_judge import (
    LLMJudge,
    LLMJudgeResult,
    get_llm_judge
)

__all__ = [
    "ProspectusKernelEvalHarness",
    "SkepticAgent",
    "JudgeFactory",
    "Dimension",
    "SkepticReport",
    "JudgeResult",
    "DimensionResult",
    "EvalReport",
    "LLMJudge",
    "LLMJudgeResult",
    "get_llm_judge"
]
