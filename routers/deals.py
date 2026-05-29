from fastapi import APIRouter
from deals import BaseCrawler, DealItem, JejuAirCrawler

router = APIRouter()


@router.get("")
def get_deals():
    crawlers: list[BaseCrawler] = [JejuAirCrawler()]
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
                "price": d.price,
                "sale_start": d.sale_start.isoformat(),
                "sale_end": d.sale_end.isoformat(),
                "booking_url": d.booking_url,
                "color": d.color,
                "image_url": d.image_url,
                "routes": [
                    {
                        "route_text": r.route_text,
                        "price": r.price,
                        "trip_type": r.trip_type,
                    }
                    for r in d.routes
                ],
            }
            for d in results
        ]
    }
