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
                "folder_structure": "JSON",
                "languages": "JSON",
                "architecture": "JSON",
                "executive_overview": "JSON",
                "analysis_evidence": "JSON",
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
        if "analysis_evidence" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE analysis_results ADD COLUMN analysis_evidence JSON")
                )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
