from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.db.session import get_session
from app.main import app
from app.models.entities import CaseRecord


def make_client_session() -> tuple[TestClient, Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), session


def test_upload_request_reports_large_local_mvp_limit():
    client, session = make_client_session()
    try:
        case = CaseRecord(case_name="Upload limit case", workflow_type="marriage_concurrent")
        session.add(case)
        session.commit()
        session.refresh(case)

        response = client.post(
            f"/api/v1/cases/{case.id}/uploads/request",
            json={
                "checklist_item_code": "photos_together",
                "original_filename": "Relationship Evidence Photo Album.pdf",
                "mime_type": "application/pdf",
                "document_language": "english",
                "has_translation": False,
            },
        )

        assert response.status_code == 201
        assert response.json()["max_upload_size_mb"] == settings.max_upload_size_mb == 100
    finally:
        app.dependency_overrides.clear()
