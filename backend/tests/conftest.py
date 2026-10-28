import os
import tempfile

os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="sapia_pytest_")
os.environ.setdefault("DATABASE_URL", "sqlite://")
