from pydantic import BaseModel, HttpUrl


class AnalyzeRequest(BaseModel):
    repo_url: HttpUrl


class AnalyzeResponse(BaseModel):
    job_id: int | None
    repository_id: int | None
    status: str
    message: str
