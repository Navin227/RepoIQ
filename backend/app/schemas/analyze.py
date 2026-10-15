from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict


class AnalyzeRequest(BaseModel):
    repo_url: Optional[str] = None
    local_path: Optional[str] = None
    analysis_run_id: Optional[str] = Field(default=None, min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class AnalyzeResponse(BaseModel):
    status: str
    analysis_run_id: Optional[str] = None
    error_code: Optional[str] = None
    repository_id: Optional[int] = None
    repo_name: Optional[str] = None
    repo_url: Optional[str] = None
    local_path: Optional[str] = None
    readme: Optional[str] = None
    readme_path: Optional[str] = None
    stack: Optional[Dict[str, Any]] = None
    folder_structure: Optional[List[Any]] = None
    languages: Optional[List[str]] = None
    overview: Optional[str] = None
    executive_overview: Optional[Dict[str, Any]] = None
    architecture: Optional[Dict[str, Any]] = None
    architecture_summary: Optional[str] = None
    modules: Optional[List[Any]] = None
    ai_insights: Optional[List[str]] = None
    similar_repositories: Optional[List[Dict[str, Any]]] = None
    analysis_evidence: Optional[Dict[str, Any]] = None
    analysis_status: Optional[str] = None
    commit_sha: Optional[str] = None
    repository_model: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
