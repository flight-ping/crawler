import pandas as pd
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / 'data' / 'countries.csv'


def load_country_map(iso_codes: set[str] | None = None) -> dict[str, dict]:
    df = pd.read_csv(DATA_PATH, encoding='utf-8-sig')
    df = df[['국제표준화기구_2자리', '한글명', '대륙명_외교부 직제']].copy()
    df.columns = ['iso2', 'name', 'continent']
    df['iso2'] = df['iso2'].str.strip()
    df = df.dropna(subset=['iso2', 'name'])
    df = df[df['iso2'] != '']
    if iso_codes:
        df = df[df['iso2'].isin(iso_codes)]
    df = df.drop_duplicates(subset='iso2')
    return df.set_index('iso2')[['name', 'continent']].to_dict('index')


if __name__ == '__main__':
    m = load_country_map()
    print(f'총 {len(m)}개')
    for k in ['KR', 'JP', 'US', 'CN', 'TH', 'VN']:
        print(f'  {k}: {m.get(k)}')
