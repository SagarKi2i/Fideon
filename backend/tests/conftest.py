import sys
import os

# Add the backend/ directory to sys.path so that `from app import ...` works
# when pytest is run from any working directory (e.g. in CI).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# `app/__init__.py` calls create_app() at import time; factory._require_secrets()
# needs DEVICE_JWT_SECRET. CI does not load backend/.env (gitignored), so set a
# deterministic value before any test module imports `app`.
os.environ.setdefault(
    "DEVICE_JWT_SECRET",
    "pytest-device-jwt-secret-must-be-non-empty-32chars",
)
