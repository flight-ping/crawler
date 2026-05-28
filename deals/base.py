from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class DealItem:
    airline: str
    title: str
    departure: str
    dest: str
    flag: str
    price: int
    sale_start: date
    sale_end: date
    booking_url: str
    color: str
    image_url: str


class BaseCrawler(ABC):

    @abstractmethod
    def crawl(self) -> list[DealItem]:
        """항공사 특가 공지 페이지를 크롤링하여 DealItem 목록 반환"""
        ...
