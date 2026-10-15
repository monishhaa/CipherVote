"""
SecureVote FastAPI Main Application.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.models.database import init_db
from app.routers import (
    admin_portal,
    auth,
    ballots,
    bulletin_board,
    election,
    public_portal,
    tally,
    trustee_ceremony,
    voter_portal,
    voters,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    await init_db()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="A Verifiable Online Voting System with Threshold Credentials, Face Liveness, and Homomorphic Encryption",
    lifespan=lifespan,
)

# CORS configuration for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Structured Two-Portal & Public Routers
app.include_router(voter_portal.router, prefix=settings.API_V1_STR)
app.include_router(admin_portal.router, prefix=settings.API_V1_STR)
app.include_router(public_portal.router, prefix=settings.API_V1_STR)
app.include_router(trustee_ceremony.router, prefix=settings.API_V1_STR)

# Legacy Routers for full backwards compatibility
app.include_router(election.router, prefix=settings.API_V1_STR)
app.include_router(voters.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(ballots.router, prefix=settings.API_V1_STR)
app.include_router(bulletin_board.router, prefix=settings.API_V1_STR)
app.include_router(tally.router, prefix=settings.API_V1_STR)



@app.get("/")
async def root():
    return {
        "system": "SecureVote API",
        "status": "online",
        "version": settings.VERSION,
        "docs": "/docs",
    }
