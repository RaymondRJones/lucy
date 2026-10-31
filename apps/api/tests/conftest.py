from __future__ import annotations

import atexit
import os
from pathlib import Path
import shutil
import tempfile

# Runs before any app import, so settings and the database engine never point at real local data.
REPO_ROOT = Path(__file__).resolve().parents[3]
SCRATCH_DIR = Path(tempfile.mkdtemp(prefix="lucy-tests-"))
atexit.register(shutil.rmtree, SCRATCH_DIR, ignore_errors=True)

(SCRATCH_DIR / "storage").mkdir()
os.environ["GREEN_CARD_PACKET_DATABASE_URL"] = f"sqlite:///{(SCRATCH_DIR / 'storage' / 'app.db').as_posix()}"
os.environ["GREEN_CARD_PACKET_UPLOAD_DIR"] = str(SCRATCH_DIR / "storage" / "uploads")
os.environ["GREEN_CARD_PACKET_GENERATED_DIR"] = str(SCRATCH_DIR / "storage" / "generated")

# Blank form templates are resolved relative to the repo root.
os.chdir(REPO_ROOT)
