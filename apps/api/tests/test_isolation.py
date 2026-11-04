from __future__ import annotations

from pathlib import Path

from app.api import routes
from app.core.config import settings
from app.db.session import engine
from app.services.packet_assembly import PACKET_OUTPUT_DIR

REAL_STORAGE = Path(__file__).resolve().parents[3] / "storage"


def test_tests_never_point_at_real_storage() -> None:
    paths = [
        settings.upload_dir,
        settings.generated_dir,
        routes.GENERATED_PDF_DIR,
        PACKET_OUTPUT_DIR,
        Path(str(engine.url.database)),
    ]

    assert not [path for path in paths if path.resolve().is_relative_to(REAL_STORAGE)]
