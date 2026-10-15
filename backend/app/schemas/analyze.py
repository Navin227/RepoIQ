
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


AnalysisStatus = Literal["ai_generated", "partial", "degraded", "error"]
ResponseStatus = Literal["success", "error"]


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    repo_url: Optional[str] = None
    local_path: Optional[str] = None
    analysis_run_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Request execution status and analysis quality are separate concepts.
    status: ResponseStatus
    analysis_run_id: Optional[str] = None
    error_code: Optional[str] = None
    message: Optional[str] = None

    # Repository identity and acquisition details.
    repository_id: Optional[int] = None
    repo_name: Optional[str] = None
    repo_url: Optional[str] = None
    local_path: Optional[str] = None
    commit_sha: Optional[str] = None

    # Repository metadata and detected technologies.
    readme: Optional[str] = None
    readme_path: Optional[str] = None
    stack: Optional[Dict[str, Any]] = None
    folder_structure: Optional[List[Any]] = None
    languages: Optional[List[str]] = None

    # AI-generated analysis.
    overview: Optional[str] = None
    executive_overview: Optional[Dict[str, Any]] = None
    architecture: Optional[Dict[str, Any]] = None
    architecture_summary: Optional[str] = None
    modules: Optional[List[Any]] = None
    ai_insights: Optional[List[str]] = None
    similar_repositories: Optional[List[Dict[str, Any]]] = None

    # Evidence and validation metadata.
    analysis_evidence: Optional[Dict[str, Any]] = None
    analysis_status: Optional[AnalysisStatus] = None
    repository_model: Optional[Dict[str, Any]] = None
