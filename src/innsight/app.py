from fastapi import FastAPI, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List

from .exceptions import ServiceUnavailableError

class WeightsModel(BaseModel):
    rating: Optional[float] = 1.0
    tier: Optional[float] = 1.0

class RecommendRequest(BaseModel):
    query: str = Field(..., description="Search query for accommodations")
    weights: Optional[WeightsModel] = None
    top_n: Optional[int] = Field(default=20, ge=1, le=20, description="Maximum number of results (1-20)")
    filters: Optional[List[str]] = None

class AccommodationModel(BaseModel):
    name: str
    score: float = Field(ge=0, le=100)
    tier: int = Field(ge=0, le=3)

class StatsModel(BaseModel):
    tier_0: int = 0
    tier_1: int = 0  
    tier_2: int = 0
    tier_3: int = 0

class RecommendResponse(BaseModel):
    stats: StatsModel
    top: List[AccommodationModel]

class ErrorResponse(BaseModel):
    error: str
    message: str

def create_app() -> FastAPI:
    app = FastAPI(title="InnSight API", root_path="/api")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify your frontend domain
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return JSONResponse(
            status_code=400,
            content={
                "error": "Parse Error",
                "message": f"Request validation failed: {str(exc)}"
            }
        )

    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_exception_handler(request, exc):
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service Unavailable",
                "message": str(exc)
            }
        )

    from .pipeline import Recommender
    def get_recommender() -> Recommender:
        return Recommender()

    @app.post("/recommend", response_model=RecommendResponse)
    async def recommend(request: RecommendRequest, r: Recommender = Depends(get_recommender)):
        return r.run(request.model_dump())

    return app

# Create the app instance for FastAPI CLI
app = create_app()
