"""
KIRIN EVAL — Framework de Avaliação Abductiva
Baseado em Augusto Galego (Groomy, Harness, Evals) + Abdução Sistêmica
"""

from .kirin_eval_harness import (
    KirinEvalHarness,
    SkepticAgent,
    JudgeFactory,
    Dimension,
    SkepticReport,
    JudgeResult,
    DimensionResult,
    EvalReport
)

__all__ = [
    "KirinEvalHarness",
    "SkepticAgent",
    "JudgeFactory",
    "Dimension",
    "SkepticReport",
    "JudgeResult",
    "DimensionResult",
    "EvalReport"
]
