from fastapi import FastAPI, Depends

def create_app() -> FastAPI:
    app = FastAPI(title="InnSight API")

    from .pipeline import Recommender
    def get_recommender() -> Recommender:
        return Recommender()

    @app.post("/recommend")
    async def recommend(query: dict, r: Recommender = Depends(get_recommender)):
        return r.run(query)

    return app

# Create the app instance for FastAPI CLI
app = create_app()
