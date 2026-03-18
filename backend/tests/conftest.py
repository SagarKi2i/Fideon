import sys
import os

# Add the backend/ directory to sys.path so that `from app import ...` works
# when pytest is run from any working directory (e.g. in CI).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
