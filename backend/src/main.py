from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
from contextlib import asynccontextmanager

from src.core.config import settings
from src.core.database import init_db
from src.core.logging import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown"""
    # Startup
    logger.info("=== VizFlow Backend Starting ===")
    logger.info(f"Demo mode: {settings.DEMO_MODE}")
    logger.info(f"Database: {settings.DB_URL}")
    logger.info(f"Datasets dir: {settings.DATASETS_DIR}")
    logger.info(f"Thumbnails dir: {settings.THUMBNAILS_DIR}")
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("=== VizFlow Backend Shutting Down ===")

app = FastAPI(
    title="VizFlow API",
    version="0.0.1",
    description="Natural language visualization workflow",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    
    logger.info(
        f"request_id={request_id} | {request.method} {request.url.path} | "
        f"status={response.status_code} | time={process_time:.2f}ms"
    )
    
    return response

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, 'request_id', 'unknown')
    logger.error(f"request_id={request_id} | Unhandled error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEMO_MODE else "An error occurred",
            "request_id": request_id
        }
    )

# Health endpoint
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "demo_mode": settings.DEMO_MODE,
        "version": "0.0.1"
    }

# Import and include routers
from src.api import datasets, charts, workflows, analysis
app.include_router(datasets.router, prefix="/api", tags=["datasets"])
app.include_router(charts.router, prefix="/api", tags=["charts"])
app.include_router(workflows.router, prefix="/api", tags=["workflows"])
app.include_router(analysis.router, prefix="/api", tags=["analysis"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
