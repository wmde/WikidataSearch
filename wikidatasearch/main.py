"""Initialize the FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from gradio.routes import mount_gradio_app

from .config import settings
from .dependencies import register_rate_limit, verify_admin_auth
from .routes import frontend, health, item, property, similarity
from .routes.admin import analytics_api_router, build_analytics_app
from .services.logger.database import initialize_database

app = FastAPI(
    title="Wikidata Vector Search",
    description="API for querying the Wikidata Vector Database",
    version="0.2.1",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={"persistAuthorization": True},
)

# Enable all Cors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

register_rate_limit(app)


# Initialize the cache on startup
@app.on_event("startup")
async def startup_event():
    """Initialize the FastAPI cache at startup."""
    initialize_database()
    FastAPICache.init(InMemoryBackend(), prefix="wikidata-cache")


# Routers
app.include_router(item.router)
app.include_router(property.router)
app.include_router(similarity.router)
app.include_router(frontend.router)
app.include_router(health.router)

frontend.mount_static(app)

if settings.ANALYTICS_API_SECRET:
    app.include_router(analytics_api_router)
    mount_gradio_app(
        app,
        build_analytics_app(),
        path="/admin",
        auth_dependency=verify_admin_auth,
        auth_message="Provide HTTP Basic auth using ANALYTICS_API_SECRET as password.",
    )
