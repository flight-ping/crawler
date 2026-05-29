from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass
class RouteItem:
    route_text: str
    price: int
    trip_type: str


@dataclass
class DealItem:
    airline: str
    title: str
    departure: str
    dest: str
    price: int
    sale_start: date
    sale_end: date
    booking_url: str
    color: str
    image_url: str
    routes: list[RouteItem] = field(default_factory=list)


class BaseCrawler(ABC):

    @abstractmethod
    def crawl(self) -> list[DealItem]:
        """항공사 특가 공지 페이지를 크롤링하여 DealItem 목록 반환"""
        ...
