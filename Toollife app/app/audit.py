import os
import logging
from .config import AUDIT_LOG_FILE, LOGS_DIR
from .db import log_audit as db_log_audit

# Ensure logs directory exists BEFORE configuring logging
os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    filename=AUDIT_LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

def log_audit(user: str, action: str):
    logging.info(f"User: {user} | Action: {action}")
    try:
        db_log_audit(user, action)
    except Exception:
        pass
