import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
CREDS_PATH = str(BASE_DIR / "account_credentials.yaml")
CLASSIC_CREDS_PATH = str(BASE_DIR / "classic_central_credentials.yaml")

# pycentral's own log level. Raise it to DEBUG to diagnose a failing run, but
# note that DEBUG includes request headers, so treat such a log as a secret.
CENTRAL_LOG_LEVEL = os.environ.get("CENTRAL_LOG_LEVEL", "ERROR")
