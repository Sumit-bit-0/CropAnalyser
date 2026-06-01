from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS, init_dirs
from api import states, crops, trends, revenue, forecast, recommend, profit, mandi, geo

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_dirs()
    yield

app = FastAPI(title="Agri Market Access Analyser API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(states.router, prefix="/api")
app.include_router(crops.router, prefix="/api")
app.include_router(trends.router, prefix="/api")
app.include_router(revenue.router, prefix="/api")
app.include_router(forecast.router, prefix="/api")
app.include_router(recommend.router, prefix="/api")
app.include_router(profit.router, prefix="/api")
app.include_router(mandi.router, prefix="/api")
app.include_router(geo.router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok"}
