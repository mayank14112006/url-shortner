import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import engine, Base
from routers import auth, urls

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title="Antigravity URL Shortener",
    description="A high-performance URL shortener using FastAPI, PostgreSQL, and Redis cache.",
    version="1.0.0"
)

# Setup CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Automatically create database tables on startup
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize database tables: {e}")

# Register API Routers
# Note: Keeping direct paths like /register, /login, /shorten, etc.
app.include_router(auth.router)
app.include_router(urls.router)

# Mount the static directory to serve frontend assets
# This creates a folder structure: project/static/index.html
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.warning(f"Could not mount static directory: {e}. Serves file fallback instead.")

@app.get("/")
def read_root():
    """Serves the single-page application frontend."""
    return FileResponse("static/index.html")
