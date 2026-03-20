"""
Funding Intelligence Agent — Agentic RAG Search Module.

3-engine parallel search (Tavily + Serper + Brave) with iterative refinement.
SearchOrchestrator is the single entry point.
"""


def __getattr__(name: str):
    """Lazy import — orchestrator.py가 아직 없어도 패키지 import 가능."""
    if name == "SearchOrchestrator":
        from src.search.orchestrator import SearchOrchestrator
        return SearchOrchestrator
    raise AttributeError(f"module 'src.search' has no attribute {name!r}")


__all__ = ["SearchOrchestrator"]
