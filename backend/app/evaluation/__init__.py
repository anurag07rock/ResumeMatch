"""
AI/ML Evaluation Suite and Benchmark Runner Package
ResumeMatch — Explainable AI-Powered Resume-to-Job Matching Platform
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.evaluation.benchmark import BenchmarkReport, BenchmarkRunner

def __getattr__(name: str):
    if name in ("BenchmarkRunner", "BenchmarkReport"):
        from app.evaluation.benchmark import BenchmarkReport, BenchmarkRunner
        return {"BenchmarkRunner": BenchmarkRunner, "BenchmarkReport": BenchmarkReport}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["BenchmarkRunner", "BenchmarkReport"]
