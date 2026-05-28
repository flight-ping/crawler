from fastapi import FastAPI
from routers import deals, flights

app = FastAPI(
    title="FlightPing Crawler",
    description="Google Flights 항공권 데이터 조회 서버",
    version="1.0.0"
)

app.include_router(deals.router,   prefix="/deals")
app.include_router(flights.router, prefix="/flights")


@app.get("/health")
def health():
    return {"status": "ok"}
