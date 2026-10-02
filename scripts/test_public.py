"""Execute the reviewed public selection; never discover/run held evaluators."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    selection = json.loads((ROOT / "config/public_tests.json").read_text())["tests"]
    if not selection or any(not item.startswith("tests/test_") for item in selection):
        raise ValueError("Invalid public regression selection")
    # API module initialization must not open a developer's database or require
    # a writable checkout. Force the actual supported test/memory configuration.
    environment = os.environ.copy()
    for key in ("OPENAI_API_KEY", "DATABASE_URL", "SESSION_DATABASE_URL"):
        environment.pop(key, None)
    environment.update({"APP_MODE": "test", "PUBLIC_DEMO": "0", "LLM_PROVIDER": "fake",
                        "CHECKPOINT_BACKEND": "memory", "CHECKPOINT_URI": "",
                        "SESSION_DB_PATH": "", "RETRIEVAL_BACKEND": "local"})
    return subprocess.call([sys.executable, "-m", "pytest", *selection, "-q", "--disable-warnings"], cwd=ROOT, env=environment)

if __name__ == "__main__": sys.exit(main())
