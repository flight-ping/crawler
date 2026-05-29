import asyncio
import re
from datetime import date, datetime
from typing import Optional

import httpx

from notifier import send_slack_alert
from .base import BaseCrawler, DealItem, RouteItem

COLOR = '#FF5713'
SCAN_END = 4000
SCAN_LOOKBACK = 300
CONCURRENCY = 10
BASE_URL = 'https://www.jejuair.net'
DETAIL_API = '/ko/event/getEventDetail.json'


# 크롤러
class JejuAirCrawler(BaseCrawler):
    """제주항공 이벤트 페이지에서 특가 공지 크롤링"""

    def crawl(self) -> list[DealItem]:
        return asyncio.run(self._crawl_async())

    #async 구현부
    async def _crawl_async(self) -> list[DealItem]:
        async with httpx.AsyncClient(
            headers=_make_headers(),
            follow_redirects=True,
            timeout=20,
        ) as client:
            await client.get(BASE_URL)

            sem = asyncio.Semaphore(CONCURRENCY)
            tasks = [
                self._process_event(client, sem, no)
                for no in range(SCAN_END, SCAN_END - SCAN_LOOKBACK, -1)
            ]
            results = await asyncio.gather(*tasks)

        return [d for d in results if d is not None]

    async def _process_event(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        event_no: int,
    ) -> Optional[DealItem]:
        async with sem:
            event_str = f'{event_no:010d}'
            html = await _fetch_event(client, event_str)
            if html is None:
                return None
            # 이벤트 제목/배너/섹션 헤더에 특가 포함 여부 확인
            if not _is_special_deal(html):
                return None
            item = _parse(html, event_str)
            if item is None or item.sale_end < date.today():
                return None
            if _is_unhandled_price_structure(html, item.routes):
                send_slack_alert(
                    f':warning: 제주항공 미처리 구조 발생\n'
                    f'이벤트: {BASE_URL}/ko/event/eventDetail.do?eventNo={event_str}\n'
                    f'제목: {item.title}'
                )
            return item


def _is_special_deal(html: str) -> bool:
    """이벤트 제목/배너 타이틀/섹션 헤더에 특가가 포함되어 있는지 확인

    이벤트 본문 전체를 검사하면 면책 문구에도 반응하여
    특가 이벤트가 아닌 멤버십/할인코드 이벤트를 오탐함
    """
    # 이벤트 제목
    nm_m = re.search(r'id="eventNm"\s+value="([^"]+)"', html)
    if nm_m and '특가' in nm_m.group(1):
        return True

    # 메인 배너 제목
    for banner in re.findall(r'class="event-banner__title"[^>]*>(.*?)</p>', html, re.DOTALL):
        if '특가' in banner:
            return True

    # 섹션 앵커 헤더
    for anchor in re.findall(r'class="event-anchor-title"[^>]*>(.*?)</div>', html, re.DOTALL):
        if '특가' in anchor:
            return True

    return False


async def _fetch_event(client: httpx.AsyncClient, event_str: str) -> Optional[str]:
    url = f'{BASE_URL}{DETAIL_API}?eventNo={event_str}'
    try:
        r = await client.post(url, data={'originReferer': ''})
    except Exception:
        return None
    html = r.text
    if len(html) < 1000 or 'event-page-banner' not in html:
        return None
    return html


def _parse(html: str, event_str: str) -> Optional[DealItem]:
    # 이벤트 제목
    title_m = re.search(r'id="eventNm"\s+value="([^"]+)"', html)
    if not title_m:
        return None
    title = title_m.group(1).strip()

    # 판매 기간
    date_m = re.search(
        r'event-banner__date[^>]*>\s*'
        r'(\d{4}\.\d{2}\.\d{2})\s*~\s*(\d{4}\.\d{2}\.\d{2})',
        html,
    )
    if not date_m:
        return None
    sale_start = datetime.strptime(date_m.group(1), '%Y.%m.%d').date()
    sale_end = datetime.strptime(date_m.group(2), '%Y.%m.%d').date()

    # 예약 URL 목록
    booking_urls = re.findall(
        r'data-(?:href|web-url|app-url|wmo-url)="\s*(https?://[^"]+Availability[^"]+)"', html
    )
    if not booking_urls:
        return None
    primary_url = booking_urls[0].replace('&amp;', '&')

    # 출발지 / 도착지 공항 코드
    dep_m = re.search(r'depStn=([A-Z]{3})', primary_url)
    arr_m = re.search(r'arrStn=([A-Z]{3})', primary_url)
    if not dep_m or not arr_m:
        return None
    dep_code = dep_m.group(1)
    arr_code = arr_m.group(1)

    # 노선별 가격 파싱
    routes = _parse_routes(html)
    price = min(r.price for r in routes if r.price > 0) if routes else 0

    if not routes:
        prices: list[int] = []
        for m in re.finditer(r'class="amount-price"[^>]*>([\d,]+)', html):
            prices.append(int(m.group(1).replace(',', '')))
        for m in re.finditer(r'class="normal"[^>]*>([\d,]+)원', html):
            prices.append(int(m.group(1).replace(',', '')))
        if not prices:
            for m in re.finditer(r'([\d,]+)원\s*(?:~|부터)', html):
                v = int(m.group(1).replace(',', ''))
                if v >= 10000:
                    prices.append(v)
        price = min(prices) if prices else 0

    # 예약 URL: 이벤트 상세 페이지
    booking_url = f'{BASE_URL}/ko/event/eventDetail.do?eventNo={event_str}'

    # 배너 이미지 URL
    img_m = re.search(
        r'event-top-banner[^>]+background-image:\s*url\(([^)]+)\)', html
    )
    image_url = img_m.group(1) if img_m else ''

    return DealItem(
        airline='제주항공',
        title=title,
        departure=dep_code,
        dest=arr_code,
        price=price,
        sale_start=sale_start,
        sale_end=sale_end,
        booking_url=booking_url,
        color=COLOR,
        image_url=image_url,
        routes=routes,
    )


def _parse_routes(html: str) -> list[RouteItem]:
    """노선별 RouteItem 목록 파싱"""
    routes: list[RouteItem] = []

    # 링크형: event-price-link (amount-head + amount-price)
    for link in re.findall(r'class="event-price-link"[^>]*>(.*?)</a>', html, re.DOTALL):
        target_m = re.search(r'class="target"[^>]*>(.*?)</div>', link, re.DOTALL)
        head_m = re.search(r'class="amount-head"[^>]*>(.*?)</div>', link, re.DOTALL)
        price_m = re.search(r'class="amount-price"[^>]*>([\d,]+)', link)
        if not target_m or not price_m:
            continue
        route_text = re.sub(r'<[^>]+>', '', target_m.group(1)).strip()
        route_text = re.sub(r'\s*-\s*', '-', route_text)
        route_text = re.sub(r'\s+', ' ', route_text)
        trip_type = '왕복'
        if head_m:
            head_text = re.sub(r'<[^>]+>', '', head_m.group(1))
            trip_type = '편도' if '편도' in head_text else '왕복'
        price = int(price_m.group(1).replace(',', ''))
        if route_text and price > 0:
            routes.append(RouteItem(route_text=route_text, price=price, trip_type=trip_type))

    if routes:
        return routes

    # 테이블형: air-line + span.normal
    for table in re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL):
        if 'air-line' not in table:
            continue
        head_m = re.search(r'class="event-tbl-head"[^>]*>(.*?)</th>', table, re.DOTALL)
        if head_m:
            head_text = re.sub(r'<[^>]+>', '', head_m.group(1))
            trip_type = '편도' if '편도' in head_text else '왕복'
        else:
            trip_type = '왕복'
        for row in re.findall(r'<tr[^>]*>(.*?)</tr>', table, re.DOTALL):
            route_m = re.search(r'class="air-line"[^>]*>(.*?)</td>', row, re.DOTALL)
            price_m = re.search(r'class="normal"[^>]*>([\d,]+)', row)
            if not route_m or not price_m:
                continue
            route_text = re.sub(r'<[^>]+>', '', route_m.group(1))
            route_text = re.sub(r'[✔✓✗]', '', route_text).strip()
            route_text = re.sub(r'\s*-\s*', '-', route_text)
            route_text = re.sub(r'\s+', ' ', route_text)
            price = int(price_m.group(1).replace(',', ''))
            if route_text and price > 0:
                routes.append(RouteItem(route_text=route_text, price=price, trip_type=trip_type))

    return routes


def _is_unhandled_price_structure(html: str, routes: list[RouteItem]) -> bool:
    if routes:
        return False
    if re.search(r'class="event-cupon-price"', html) and \
       not re.search(r'class="(?:event-price-link|air-line)"', html):
        return False
    if re.search(r'class="event-price-link"', html):
        return True
    if re.search(r'class="air-line"', html) and re.search(r'class="amount-price"', html):
        return True
    return False


def _make_headers() -> dict[str, str]:
    return {
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
