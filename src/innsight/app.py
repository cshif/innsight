from fastapi import FastAPI, Depends
from pydantic import BaseModel, Field
from typing import Optional, List

class WeightsModel(BaseModel):
    rating: Optional[float] = 1.0
    tier: Optional[float] = 1.0

class RecommendRequest(BaseModel):
    query: str = Field(..., description="Search query for accommodations")
    weights: Optional[WeightsModel] = None
    top_n: Optional[int] = Field(default=20, le=20, description="Maximum number of results")

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

def create_app() -> FastAPI:
    app = FastAPI(title="InnSight API")

    from .pipeline import Recommender
    def get_recommender() -> Recommender:
        return Recommender()

    @app.post("/recommend", response_model=RecommendResponse)
    async def recommend(request: RecommendRequest, r: Recommender = Depends(get_recommender)):
        return r.run(request.model_dump())

    return app

# Create the app instance for FastAPI CLI
app = create_app()
