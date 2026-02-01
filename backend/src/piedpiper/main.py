from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from piedpiper.api.routes import router as api_router
from piedpiper.review.router import router as review_router
from piedpiper.config import settings
from piedpiper.infra.redis import EmbeddingService, HybridKnowledgeBase

logger = logging.getLogger(__name__)


class AppState:
    """Global application state for dependency injection."""
    redis: Redis | None = None
    embedding_service: EmbeddingService | None = None
    knowledge_base: HybridKnowledgeBase | None = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup: initialize connections
    logger.info("Initializing Redis connection...")
    try:
        app_state.redis = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=False,  # We'll handle encoding ourselves
        )
        await app_state.redis.ping()
        logger.info(f"✓ Redis connected: {settings.redis_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

    # Initialize embedding service
    logger.info("Initializing embedding service...")
    app_state.embedding_service = EmbeddingService(
        openai_api_key=settings.openai_api_key,
        redis_client=app_state.redis,
    )
    logger.info("✓ Embedding service initialized")

    # Initialize hybrid knowledge base
    logger.info("Initializing hybrid knowledge base...")
    app_state.knowledge_base = HybridKnowledgeBase(
        redis_client=app_state.redis,
        embedding_service=app_state.embedding_service,
    )
    
    # Create search indices
    try:
        await app_state.knowledge_base.initialize_indices()
        logger.info("✓ Redis search indices created")
    except Exception as e:
        logger.warning(f"Failed to create search indices (may already exist): {e}")
    
    # TODO: init Postgres, Weave
    
    yield
    
    # Shutdown: close connections
    logger.info("Shutting down...")
    if app_state.redis:
        await app_state.redis.close()
        logger.info("✓ Redis connection closed")
    # TODO: cleanup Postgres, Weave


app = FastAPI(
    title="PiedPiper - AI Focus Group Simulation",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.include_router(review_router, prefix="/api/review")
