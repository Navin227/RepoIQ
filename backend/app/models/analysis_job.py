from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalysisJobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repo_url: Mapped[str] = mapped_column(String(500), index=True)
    status: Mapped[AnalysisJobStatus] = mapped_column(Enum(AnalysisJobStatus), default=AnalysisJobStatus.queued)
    repository_id: Mapped[int | None] = mapped_column(ForeignKey("repositories.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
