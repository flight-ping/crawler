from fastapi import FastAPI

app = FastAPI(
    title="FlightPing Crawler",
    description="Google Flights 항공권 데이터 조회 서버",
    version="1.0.0"
)


@app.get("/health")
def health():
    return {"status": "ok"}
