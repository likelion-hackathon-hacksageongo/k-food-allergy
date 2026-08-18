#!/usr/bin/env python3
"""
농림수산식품교육문화정보원 레시피 API 전량 수집 → raw/ 캐시.

    python3 data/scripts/fetch_epis.py
    python3 data/scripts/fetch_epis.py --refresh   # 캐시 무시하고 다시 받기

식품안전나라(COOKRCP01)와 달리 재료가 한 행씩 구조화되어 오고,
IRDNT_TY_NM(주재료/부재료/양념)이 명시되어 있어 파싱이 필요 없습니다.

    기본정보  Grid_...226_1   537 레시피   RECIPE_NM_KO, NATION_NM, TY_NM …
    재료정보  Grid_...227_1  6104 재료행   IRDNT_NM, IRDNT_CPCTY, IRDNT_TY_NM

이용허락범위 제한 없음(무료). data/.env 의 EPIS_API_KEY 를 씁니다.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = DATA_DIR / '.env'
RAW = DATA_DIR / 'raw'

BASE = 'http://211.237.50.150:7080/openapi'
GRIDS = {
    'recipes': ('Grid_20150827000000000226_1', '기본정보'),
    'ingredients': ('Grid_20150827000000000227_1', '재료정보'),
    'steps': ('Grid_20150827000000000228_1', '과정정보'),
}
PAGE_SIZE = 1000


def load_key():
    key = os.environ.get('EPIS_API_KEY')
    if key:
        return key.strip()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            name, _, value = line.partition('=')
            if name.strip() == 'EPIS_API_KEY':
                return value.strip().strip('"').strip("'")
    raise SystemExit(
        'EPIS_API_KEY 를 찾지 못했습니다.\n'
        f'  {ENV_FILE} 에 EPIS_API_KEY=발급키 를 넣으세요. (data/.env.example 참고)'
    )


def fetch_page(key, grid, start, end):
    url = f'{BASE}/{key}/json/{grid}/{start}/{end}'
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as error:
        raise SystemExit(f'요청 실패 ({grid} {start}-{end}): {error}')

    if grid not in payload:
        result = payload.get('result', {})
        raise SystemExit(f'API 오류 {result.get("code")}: {result.get("message")}')

    block = payload[grid]
    result = block.get('result', {})
    if result.get('code') not in ('INFO-000', None):
        raise SystemExit(f'API 오류 {result.get("code")}: {result.get("message")}')
    return block.get('row', []), int(block.get('totalCnt', 0))


def fetch_all(key, grid, label):
    rows, start, total = [], 1, None
    while total is None or start <= total:
        end = start + PAGE_SIZE - 1
        page, total = fetch_page(key, grid, start, end)
        if not page:
            break
        rows.extend(page)
        print(f'  {label} {start}-{min(end, total)} → 누적 {len(rows)}/{total}')
        start = end + 1
    if len(rows) != total:
        print(f'  ⚠ {label}: 수신 {len(rows)}건이 totalCnt {total}건과 다릅니다')
    return rows


def main():
    parser = argparse.ArgumentParser(description='EPIS 레시피 API 전량 수집')
    parser.add_argument('--refresh', action='store_true', help='캐시가 있어도 다시 받기')
    parser.add_argument('--skip-steps', action='store_true',
                        help='조리 과정정보는 건너뛰기 (알레르겐에는 불필요)')
    args = parser.parse_args()

    key = load_key()
    RAW.mkdir(parents=True, exist_ok=True)
    summary = {}

    for name, (grid, label) in GRIDS.items():
        if name == 'steps' and args.skip_steps:
            continue
        out = RAW / f'epis_{name}.json'
        if out.exists() and not args.refresh:
            cached = json.loads(out.read_text(encoding='utf-8'))
            print(f'캐시 사용: {out.name} ({len(cached)}건)')
            summary[name] = len(cached)
            continue
        print(f'{label} 수집 중…')
        rows = fetch_all(key, grid, label)
        out.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
        print(f'  → {out} 저장 ({len(rows)}건)')
        summary[name] = len(rows)

    print('\n=== 수집 결과 ===')
    for name, count in summary.items():
        print(f'  {GRIDS[name][1]:<8} {count:>6}건')

    recipes = json.loads((RAW / 'epis_recipes.json').read_text(encoding='utf-8'))
    nations, types = {}, {}
    for r in recipes:
        nations[r.get('NATION_NM', '')] = nations.get(r.get('NATION_NM', ''), 0) + 1
        types[r.get('TY_NM', '')] = types.get(r.get('TY_NM', ''), 0) + 1
    print('\n국가별:')
    for k, v in sorted(nations.items(), key=lambda x: -x[1]):
        print(f'  {k or "(빈값)":<10} {v}')
    print('\n요리 분류별:')
    for k, v in sorted(types.items(), key=lambda x: -x[1]):
        print(f'  {k or "(빈값)":<18} {v}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
