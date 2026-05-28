from fastapi import FastAPI, HTTPException, Query
from fli.models import (
    Airport, PassengerInfo, SeatType,
    MaxStops, SortBy, FlightSearchFilters, FlightSegment
)
from fli.search import SearchFlights
from deals import BaseCrawler, DealItem

app = FastAPI(
    title="FlightPing Crawler",
    description="Google Flights 항공권 데이터 조회 서버",
    version="1.0.0"
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/deals")
def get_deals():
    crawlers: list[BaseCrawler] = []
    results: list[DealItem] = []
    for crawler in crawlers:
        try:
            results.extend(crawler.crawl())
        except Exception as e:
            print(f"Crawler error ({crawler.__class__.__name__}): {e}")
    return {
        "deals": [
            {
                "airline": d.airline,
                "title": d.title,
                "departure": d.departure,
                "dest": d.dest,
                "flag": d.flag,
                "price": d.price,
                "sale_start": d.sale_start.isoformat(),
                "sale_end": d.sale_end.isoformat(),
                "booking_url": d.booking_url,
                "color": d.color,
            }
            for d in results
        ]
    }


@app.get("/flights")
def get_flights(
        departure: str = Query(..., description="출발 공항 코드 (예: ICN)"),
        destination: str = Query(..., description="도착 공항 코드 (예: NRT)"),
        date: str = Query(..., description="출발 날짜 (YYYY-MM-DD)"),
):
    try:
        departure_airport = Airport[departure.upper()]
        destination_airport = Airport[destination.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 공항 코드입니다.")

    filters = FlightSearchFilters(
        passenger_info=PassengerInfo(adults=1),
        flight_segments=[
            FlightSegment(
                departure_airport=[[departure_airport, 0]],
                arrival_airport=[[destination_airport, 0]],
                travel_date=date,
            )
        ],
        seat_type=SeatType.ECONOMY,
        stops=MaxStops.ANY,
        sort_by=SortBy.CHEAPEST,
    )

    search = SearchFlights()
    results = search.search(filters, currency="KRW", language="ko", country="KR")

    if not results:
        return {"flights": []}

    flights = []
    for flight in results:
        legs = []
        for leg in flight.legs:
            legs.append({
                "airline": leg.airline.name if leg.airline else None,
                "flightNumber": leg.flight_number,
                "departure": leg.departure_datetime.isoformat() if leg.departure_datetime else None,
                "arrival": leg.arrival_datetime.isoformat() if leg.arrival_datetime else None,
            })
        flights.append({
            "price": flight.price,
            "duration": flight.duration,
            "stops": flight.stops,
            "legs": legs,
        })

    return {"flights": flights}
