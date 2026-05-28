from fastapi import APIRouter, HTTPException, Query
from fli.models import (
    Airport, PassengerInfo, SeatType,
    MaxStops, SortBy, FlightSearchFilters, FlightSegment,
)
from fli.search import SearchFlights

router = APIRouter()


@router.get("")
def get_flights(
        departure: str = Query(..., description="출발 공항 코드"),
        destination: str = Query(..., description="도착 공항 코드"),
        date: str = Query(..., description="출발 날짜 (YYYY-MM-DD)"),
):
    try:
        departure_airport = Airport[departure.upper()]
        destination_airport = Airport[destination.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail="유효하지 않은 공항 코드입니다.")

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
        legs = [
            {
                "airline": leg.airline.name if leg.airline else None,
                "flightNumber": leg.flight_number,
                "departure": leg.departure_datetime.isoformat() if leg.departure_datetime else None,
                "arrival": leg.arrival_datetime.isoformat() if leg.arrival_datetime else None,
            }
            for leg in flight.legs
        ]
        flights.append({
            "price": flight.price,
            "duration": flight.duration,
            "stops": flight.stops,
            "legs": legs,
        })

    return {"flights": flights}
