import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
REPO_ROOT = ROOT_DIR.parent
HCA_SRC_DIR = REPO_ROOT / "hca" / "src"

for path in (str(REPO_ROOT), str(HCA_SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

load_dotenv(ROOT_DIR / ".env")