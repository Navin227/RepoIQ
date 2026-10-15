from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from app.models import AnalysisJob, AnalysisResult, Repository  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            for column_name, column_type in {
                "readme": "TEXT",
                "readme_path": "TEXT",
                "folder_structure": "JSON",
                "languages": "JSON",
                "architecture": "JSON",
                "executive_overview": "JSON",
                "analysis_evidence": "JSON",
                "analysis_status": "TEXT",
                "commit_sha": "TEXT",
                "repository_model": "JSON",
            }.items():
                connection.execute(
                    text(
                        f"ALTER TABLE analysis_results ADD COLUMN IF NOT EXISTS "
                        f'"{column_name}" {column_type}'
                    )
                )
    elif engine.dialect.name == "sqlite":
        columns = {
            column["name"]
            for column in inspect(engine).get_columns("analysis_results")
        }
        additions = {"analysis_evidence": "JSON", "analysis_status": "TEXT", "commit_sha": "TEXT", "repository_model": "JSON", "readme_path": "TEXT"}
        if any(name not in columns for name in additions):
            with engine.begin() as connection:
                for name, kind in additions.items():
                    if name not in columns:
                        connection.execute(text(f"ALTER TABLE analysis_results ADD COLUMN {name} {kind}"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
