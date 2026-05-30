# 사용법: python scripts/seed_airports.py [--backend http://localhost:8080]

import argparse
import csv
import io
import re

import httpx

BACKEND_URL = 'http://localhost:8080'

KAC_ROUTEMAP_URL = 'https://www.airport.co.kr/gimpo/cms/frRouteMapCon/routeMap.do'
KAC_AIRPORT_DATA_URL = 'https://www.airport.co.kr/gimpo/ajaxf/frRouteMapSvc/getAirportData.do'
OURAIRPORTS_CSV_URL = 'https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv'

KAC_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': KAC_ROUTEMAP_URL,
    'Content-Type': 'application/x-www-form-urlencoded',
}


def fetch_iata_iso_map() -> dict[str, str]:
    r = httpx.get(OURAIRPORTS_CSV_URL, timeout=30, follow_redirects=True)
    r.raise_for_status()
    reader = csv.DictReader(io.StringIO(r.text))
    return {
        row['iata_code'].strip(): row['iso_country'].strip()
        for row in reader
        if row.get('iata_code', '').strip() and row.get('iso_country', '').strip()
    }


def parse_departure_airports(html: str) -> list[tuple[str, str]]:
    m = re.search(r'name=["\']startAirPort["\'][^>]*>(.*?)</select>', html, re.DOTALL)
    if not m:
        return []
    return [
        (code, name.strip())
        for code, name in re.findall(
            r'<option[^>]*value="([A-Z]{3})"[^>]*>([^<]+)</option>', m.group(1)
        )
    ]


def parse_name_map(html: str) -> dict[str, str]:
    # KAC 페이지 내 airportList JS 객체
    m = re.search(r'var\s+airportList\s*=\s*(\{[^;]+\})\s*;', html, re.DOTALL)
    if not m:
        return {}
    return {
        code: name
        for code, name in re.findall(r"code:'([A-Z]{3})'[^}]*?name:'([^']+)'", m.group(1))
    }


def query_destinations(client: httpx.Client, dep_code: str) -> list[dict]:
    try:
        r = client.post(KAC_AIRPORT_DATA_URL, data={'airPortCd': dep_code})
        data = r.json().get('data', {})
        results = []
        for section in ('dome', 'inte'):
            for item in data.get(section, []):
                code = item.get('CITY_CODE', '').strip()
                city = item.get('CITY_KOR', '').strip()
                if code:
                    results.append({'code': code, 'city': city})
        return results
    except Exception as e:
        print(f'[WARN] {dep_code} API 호출 실패: {e}')
        return []


def seed(backend_url: str) -> None:
    iata_iso = fetch_iata_iso_map()

    with httpx.Client(headers=KAC_HEADERS, timeout=15) as client:
        print('KAC 노선도 파싱 중...')
        page = client.get(KAC_ROUTEMAP_URL)
        initial = parse_departure_airports(page.text)
        name_map = parse_name_map(page.text)

        for code, name in initial:
            name_map[code] = name  # select 이름 우선

        queued: set[str] = {code for code, _ in initial}
        done: set[str] = set()
        all_airports: dict[str, str] = {}
        all_routes: list[dict] = []  # (departureCode, arrivalCode) 쌍

        # KR 공항이 도착지로 발견되면 출발지로 추가해 재조회 (ICN 등 KAC 비관리 공항 커버)
        while queued:
            dep = queued.pop()
            done.add(dep)

            for d in query_destinations(client, dep):
                code, city = d['code'], d['city']
                if code not in all_airports:
                    all_airports[code] = city
                all_routes.append({'departureCode': dep, 'arrivalCode': code})
                if iata_iso.get(code) == 'KR' and code not in done and code not in queued:
                    queued.add(code)

            if dep not in all_airports:
                all_airports[dep] = name_map.get(dep, dep)

    # KAC 공식 한국어명 우선 적용
    for code in all_airports:
        if code in name_map:
            all_airports[code] = name_map[code]

    # 공항 시딩
    airports = []
    for code in sorted(all_airports):
        iso = iata_iso.get(code, '')
        if not iso:
            print(f'[WARN] ISO 코드 없음: {code}({all_airports[code]})')
        airports.append({'code': code, 'city': all_airports[code], 'isoCode': iso})

    print(f'공항 {len(airports)}개 시딩 중...')
    r = httpx.post(f'{backend_url}/api/internal/airports/seed', json=airports, timeout=30)
    r.raise_for_status()
    result = r.json()
    print(f'  → 신규: {result.get("created")}, 갱신: {result.get("updated")}')

    # 노선 시딩
    print(f'노선 {len(all_routes)}개 시딩 중...')
    r = httpx.post(f'{backend_url}/api/internal/routes/seed', json=all_routes, timeout=30)
    r.raise_for_status()
    result = r.json()
    print(f'  → 신규: {result.get("created")}, 중복 스킵: {result.get("skipped")}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', default=BACKEND_URL)
    args = parser.parse_args()
    seed(args.backend)
