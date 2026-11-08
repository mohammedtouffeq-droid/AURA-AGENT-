import sys
from pathlib import Path

# Add project root directory to path so aura modules resolve cleanly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from aura_web import AuraWebHandler

class handler(AuraWebHandler):
    pass

app = handler
