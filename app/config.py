import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "sales_transactions.csv"
DEFAULT_DB_PATH = Path(os.getenv("BI_DB_PATH", str(PROJECT_ROOT / "data" / "sales.db")))

MAX_RESULT_ROWS = 200
ALLOWED_TABLES = {"transactions", "rejected_rows"}
CURRENCY = "INR"

STATUS_COMPLETED = "Completed"
STATUS_RETURNED = "Returned"
ALLOWED_STATUSES = {"completed", "returned", "cancelled", "pending", "refunded"}


def llm_settings():
    """Read LLM settings that belong to *this project* only.

    The agent runtime variables (MCAI_*) are deliberately ignored; users must
    provide their own USER_LLM_* values through the environment or a .env file.
    """
    api_key = os.getenv("USER_LLM_API_KEY")
    base_url = os.getenv("USER_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("USER_LLM_MODEL", "gpt-4o-mini")
    timeout = float(os.getenv("USER_LLM_TIMEOUT", "20"))
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "timeout": timeout,
        "enabled": bool(api_key),
    }
