from pydantic import BaseModel
from typing import Optional, List, Any, Dict


class AnalyzeRequest(BaseModel):
    repo_url: Optional[str] = None
    local_path: Optional[str] = None


class AnalyzeResponse(BaseModel):
    status: str
    repository_id: Optional[int] = None
    repo_name: Optional[str] = None
    repo_url: Optional[str] = None
    local_path: Optional[str] = None
    readme: Optional[str] = None
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
    message: Optional[str] = None
