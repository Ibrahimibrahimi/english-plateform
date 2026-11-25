import os
import tempfile

# Ensure tests use isolated DB before app import
_fd, _path = tempfile.mkstemp(prefix="sb-test-", suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_path}"
