from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from piedpiper.api.routes import router as api_router
from piedpiper.review.router import router as review_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize connections
    # TODO: init Redis, Postgres, Weave
    yield
    # Shutdown: close connections
    # TODO: cleanup


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
