from app.agents.base import AgentFinding, AgentResult, AnalysisContext, BaseAnalysisAgent
from app.agents.code_quality import CodeQualityAgent
from app.agents.code_review import CodeReviewAgent
from app.agents.code_understanding import CodeUnderstandingAgent
from app.agents.security import SecurityAgent
from app.agents.security_detection import SecurityDetectionAgent


def __getattr__(name: str):
    if name == "AnalysisOrchestrator":
        from app.agents.orchestrator import AnalysisOrchestrator
        return AnalysisOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseAnalysisAgent",
    "AnalysisContext",
    "AgentFinding",
    "AgentResult",
    "CodeUnderstandingAgent",
    "CodeReviewAgent",
    "CodeQualityAgent",
    "SecurityAgent",
    "SecurityDetectionAgent",
    "AnalysisOrchestrator",
]
