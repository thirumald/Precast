import os
import sys
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["PRECAST_DB"] = str(Path(_tmp) / "test.db")
os.environ["PRECAST_LLM_ENABLED"] = "0"
os.environ["PRECAST_STATIC"] = str(Path(_tmp) / "no-static")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
