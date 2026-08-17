#!/usr/bin/env python3
"""
식품안전나라 조리식품 레시피 DB(COOKRCP01) 전량 수집 → raw/ 캐시.

    # data/.env 에 FOODSAFETY_API_KEY 를 넣고
    python3 data/scripts/fetch_foodsafety.py

    # 캐시가 있어도 다시 받기
    python3 data/scripts/fetch_foodsafety.py --refresh

API 는 한 번에 최대 1000건까지 주므로 페이지를 나눠 받고, 전량을 하나의
JSON 으로 raw/foodsafety_recipes.json 에 저장합니다. raw/ 는 gitignore
대상이라 커밋되지 않으며, 키도 저장 파일에 남지 않습니다.
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent
CACHE = DATA_DIR / 'raw' / 'foodsafety_recipes.json'
ENV_FILE = DATA_DIR / '.env'

SERVICE_ID = 'COOKRCP01'
BASE = 'http://openapi.foodsafetykorea.go.kr/api'
PAGE_SIZE = 1000


def load_key():
    key = os.environ.get('FOODSAFETY_API_KEY')
    if key:
        return key.strip()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            name, _, value = line.partition('=')
            if name.strip() == 'FOODSAFETY_API_KEY':
                return value.strip().strip('"').strip("'")
    raise SystemExit(
        'API 키를 찾지 못했습니다.\n'
        f'  cp {ENV_FILE.parent.name}/.env.example {ENV_FILE.parent.name}/.env\n'
        '  그리고 FOODSAFETY_API_KEY 를 채우세요. (또는 환경변수로 지정)'
    )


def fetch_page(key, start, end):
    url = f'{BASE}/{key}/{SERVICE_ID}/json/{start}/{end}'
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as error:
        raise SystemExit(f'요청 실패 ({start}-{end}): {error}')

    service = payload.get(SERVICE_ID)
    if not service:
        raise SystemExit(f'예상하지 못한 응답입니다: {list(payload)[:3]}')

    result = service.get('RESULT', {})
    if result.get('CODE') not in ('INFO-000', None):
        raise SystemExit(f'API 오류 {result.get("CODE")}: {result.get("MSG")}')

    return service.get('row', []), int(service.get('total_count', 0))


def main():
    parser = argparse.ArgumentParser(description='식품안전나라 레시피 DB 수집')
    parser.add_argument('--refresh', action='store_true', help='캐시가 있어도 다시 받기')
    parser.add_argument('--out', type=Path, default=CACHE, help='저장 경로')
    args = parser.parse_args()

    if args.out.exists() and not args.refresh:
        cached = json.loads(args.out.read_text(encoding='utf-8'))
        print(f'캐시 사용: {args.out} ({len(cached)}건)')
        print('다시 받으려면 --refresh 를 쓰세요.')
        return 0

    key = load_key()
    rows, total = fetch_page(key, 1, PAGE_SIZE)
    print(f'전체 {total}건 중 {len(rows)}건 수신')

    start = PAGE_SIZE + 1
    while start <= total:
        end = min(start + PAGE_SIZE - 1, total)
        page, _ = fetch_page(key, start, end)
        rows.extend(page)
        print(f'  {start}-{end} → 누적 {len(rows)}건')
        start = end + 1

    if len(rows) != total:
        print(f'⚠ 수신 {len(rows)}건이 total_count {total}건과 다릅니다')

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
    print(f'\n{args.out} 에 {len(rows)}건 저장했습니다.')

    categories = {}
    for row in rows:
        categories[row.get('RCP_PAT2', '')] = categories.get(row.get('RCP_PAT2', ''), 0) + 1
    print('\n요리 종류 분포:')
    for name, count in sorted(categories.items(), key=lambda c: -c[1]):
        print(f'  {name or "(빈값)":<10} {count}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
