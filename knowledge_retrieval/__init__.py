"""AI Knowledge Architect - High-Efficiency Local Markdown Knowledge Retrieval System."""

from knowledge_retrieval.api import KnowledgeEngine
from knowledge_retrieval.models import (
    ContextExcerpt,
    ContextPackage,
    Document,
    DocumentLink,
    DocumentOutline,
    DocumentOutlineNode,
    IndexStats,
    IntegrityIssue,
    IntegrityReport,
    SearchResult,
    Section,
)

from knowledge_retrieval.agent import (
    AgentExecutionReport,
    AgentOperation,
    AgentPlan,
    InspectionResult,
    KnowledgeAgent,
)
from knowledge_retrieval.auto_update_models import (
    CandidateStatus,
    ChangeCandidate,
    ChangeType,
    KnowledgeUpdateRecord,
    MonitoredSource,
    PolicyDecision,
    ReviewQueueItem,
    RiskLevel,
    SourceType,
    TrustTier,
)
from knowledge_retrieval.auto_update_store import AutoUpdateStore
from knowledge_retrieval.auto_updater import AutoUpdater
from knowledge_retrieval.profile import (
    KnowledgeLibraryProfile,
    LibraryPermissions,
    OrganizationRule,
    QualityRules,
)

__all__ = [
    "KnowledgeEngine",
    "KnowledgeAgent",
    "KnowledgeLibraryProfile",
    "LibraryPermissions",
    "QualityRules",
    "OrganizationRule",
    "InspectionResult",
    "AgentPlan",
    "AgentOperation",
    "AgentExecutionReport",
    "Document",
    "Section",
    "DocumentLink",
    "SearchResult",
    "ContextExcerpt",
    "ContextPackage",
    "DocumentOutline",
    "DocumentOutlineNode",
    "IndexStats",
    "IntegrityIssue",
    "IntegrityReport",
    "MonitoredSource",
    "ChangeCandidate",
    "KnowledgeUpdateRecord",
    "ReviewQueueItem",
    "SourceType",
    "TrustTier",
    "ChangeType",
    "RiskLevel",
    "PolicyDecision",
    "CandidateStatus",
    "AutoUpdateStore",
    "AutoUpdater",
]

__version__ = "0.1.0"
