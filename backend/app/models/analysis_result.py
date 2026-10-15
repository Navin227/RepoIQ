from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), unique=True, index=True)
    stack: Mapped[dict] = mapped_column(JSON)
    overview: Mapped[str] = mapped_column(Text)
    modules: Mapped[list] = mapped_column(JSON)
    architecture_summary: Mapped[str] = mapped_column(Text)
    similar_repositories: Mapped[list] = mapped_column(JSON)
    readme: Mapped[str | None] = mapped_column(Text, nullable=True)
    readme_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    folder_structure: Mapped[list | None] = mapped_column(JSON, nullable=True)
    languages: Mapped[list | None] = mapped_column(JSON, nullable=True)
    architecture: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    executive_overview: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(Text, nullable=True)
    repository_model: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    repository = relationship("Repository", back_populates="analysis_result")
