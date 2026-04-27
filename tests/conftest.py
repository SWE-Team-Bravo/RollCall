## used to configure pytest running in the tests/ directory, allowing imports from the main codebase
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_client_patcher = patch("utils.db.get_client", return_value=None)
_client_patcher.start()
