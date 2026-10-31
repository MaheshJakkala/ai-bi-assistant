import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .assistant import SUPPORTED_EXAMPLES, QuestionError, answer_question
from .config import DEFAULT_CSV_PATH, DEFAULT_DB_PATH, PROJECT_ROOT, resolve_db_path
from .db import dataset_stats, get_connection, init_db, is_empty
from .ingest import CsvValidationError, load_csv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bi-assistant")

STATIC_DIR = PROJECT_ROOT / "app" / "static"

DB_PATH = resolve_db_path(DEFAULT_DB_PATH, DEFAULT_CSV_PATH)


def _ensure_database():
    """Create and seed the database if it is missing or empty.

    Safe to call repeatedly: seeding only happens when the table is empty, so a
    warm serverless instance reuses the copy already in ``/tmp``.
    """
    init_db(DB_PATH)
    with get_connection(DB_PATH) as conn:
        if is_empty(conn):
            if not DEFAULT_CSV_PATH.exists():
                raise RuntimeError(f"Seed CSV not found: {DEFAULT_CSV_PATH}")
            report = load_csv(DEFAULT_CSV_PATH, DB_PATH, replace=True)
            logger.info("Seeded database at %s: %s", DB_PATH, report)


@asynccontextmanager
async def lifespan(app):
    _ensure_database()
    yield


app = FastAPI(
    title="Mini AI Business Intelligence Assistant",
    description="Ask natural-language questions about sales transactions.",
    version="1.0.0",
    lifespan=lifespan,
)


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, examples=["What is the total revenue?"])


class QuestionResponse(BaseModel):
    question: str
    intent: str
    answer: str
    data: list
    sql: str
    interpreted_by: str
    filters: dict
    generated_at: str


@app.exception_handler(QuestionError)
async def question_error_handler(request: Request, exc: QuestionError):
    return JSONResponse(status_code=422, content={"error": "unsupported_question", "detail": str(exc)})


@app.get("/api/health")
def health():
    with get_connection(DB_PATH) as conn:
        stats = dataset_stats(conn)
    return {"status": "ok", "dataset": stats}


@app.get("/api/examples")
def examples():
    return {"examples": SUPPORTED_EXAMPLES}


@app.post("/api/ask", response_model=QuestionResponse)
def ask(payload: QuestionRequest):
    try:
        with get_connection(DB_PATH, read_only=True) as conn:
            return answer_question(conn, payload.question)
    except QuestionError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to answer question")
        raise HTTPException(status_code=500, detail=f"Could not answer the question: {exc}")


class ReloadRequest(BaseModel):
    csv_path: str | None = None


@app.post("/api/admin/reload")
def reload_dataset(payload: ReloadRequest | None = None):
    csv_path = Path(payload.csv_path) if payload and payload.csv_path else DEFAULT_CSV_PATH
    try:
        report = load_csv(csv_path, DB_PATH, replace=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CsvValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "reloaded", "report": report}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
