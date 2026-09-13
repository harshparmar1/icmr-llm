import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import settings, BASE_DIR
from backend.app.database.session import init_db
from backend.app.api.router import api_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("icmr_stw_ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown event lifecycle handler.
    Initializes database tables and verifies directory structures.
    """
    logger.info(f"Starting {settings.PROJECT_NAME} (v{settings.VERSION})...")
    logger.info(f"Environment: {settings.ENVIRONMENT} | LLM Provider: {settings.LLM_PROVIDER}")
    
    # Ensure data directories exist
    settings.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    settings.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    settings.DATA_METADATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize DB tables
    init_db()
    
    # Pre-warm Embedding model and Vector Retriever in memory for instant responses
    try:
        from backend.app.rag.embeddings import get_embedding_service
        from backend.app.api.endpoints.chat import get_chat_retriever
        logger.info("Pre-warming clinical embedding model and retriever in memory...")
        emb = get_embedding_service()
        _ = emb.model
        retriever = get_chat_retriever()
        _ = retriever.retrieve("warmup query", top_k=1)
        logger.info("Retriever and embedding models warmed up. System ready for instant queries.")
    except Exception as e:
        logger.warning(f"Retriever pre-warming non-critical warning: {e}")
    
    yield
    
    logger.info("Shutting down ICMR-STW AI service...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Evidence-grounded Clinical Decision Support & Standard Treatment Workflow "
        "Intelligence System based on official ICMR guidelines."
    ),
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_and_safety_headers(request: Request, call_next):
    """
    Injects standard security headers and mandatory ICMR clinical guidance notice.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Clinical-Safety"] = "ICMR-Evidence-Grounded-Only"
    return response


# Mount Frontend Static Assets
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", tags=["System"])
def root(request: Request):
    """
    Serves the modern clinical web UI for browsers, or returns operational metadata for API clients.
    """
    accept = request.headers.get("accept", "")
    if "text/html" in accept and not accept.startswith("*/*"):
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
    return {
        "system": settings.PROJECT_NAME,
        "short_name": settings.PROJECT_SHORT_NAME,
        "version": settings.VERSION,
        "status": "operational",
        "docs_url": "/docs",
        "ui_url": "/ui",
        "disclaimer": settings.CLINICAL_SAFETY_DISCLAIMER
    }


@app.get("/ui", tags=["System"], response_class=FileResponse)
def clinical_ui():
    """Direct route to access the Clinical Decision Support Web UI."""
    index_file = FRONTEND_DIR / "index.html"
    return FileResponse(str(index_file))


# Include API routes
app.include_router(api_router)
