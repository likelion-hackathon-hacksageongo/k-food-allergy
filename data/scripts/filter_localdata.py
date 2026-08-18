#!/usr/bin/env python3
"""
LOCALDATA(지방행정 인허가데이터) → 홍대 MVP 식당 후보 추출.

원본은 JSON(공공데이터포털 다운로드) 또는 CSV 모두 지원합니다.

    # 1) 후보 뽑기 — 사람이 검토할 candidates.csv 생성 (review/ 는 gitignore)
    python3 data/scripts/filter_localdata.py \
        "data/raw/서울시 마포구 일반음식점 인허가 정보.json" \
        --out data/review/candidates.csv --top 60

    # 2) 사람이 candidates.csv 에서 key / name 채우고 _keep 에 y 표시

    # 3) 확정본을 restaurants.csv 로 승격
    python3 data/scripts/filter_localdata.py --promote data/review/candidates.csv \
        --out data/curated/restaurants.csv

선별 기준 (MVP):
    범위  홍대입구역 반경 800m — 외국인 관광객 밀집 구역
    랭킹  시설총규모(영업장 면적) 내림차순 — 좌석 수 ∝ 방문자 수용량
          LOCALDATA에 방문자수·매출 필드가 없어 면적을 대리지표로 사용.
          100% 채워진 유일한 정량 필드이기도 함.
"""

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = DATA_DIR / '.env'
API_CACHE = DATA_DIR / 'raw' / 'localdata_mapo.json'

# 서울 열린데이터광장 — 마포구 일반음식점 인허가 정보
# 매일 갱신(3일 전 자료 기준)이라 폐업·신규가 반영됩니다.
# 좌표는 중부원점TM(EPSG:5174), 위경도는 제공하지 않음 — 공식 명세서 확인 완료.
SEOUL_API = 'http://openapi.seoul.go.kr:8088'
SEOUL_SERVICE = 'LOCALDATA_072404_MP'
API_PAGE_SIZE = 1000

HONGDAE = (37.5570, 126.9240)   # 홍대입구역
DEG_TO_M = 111_000

# LOCALDATA JSON 은 소문자 키, CSV 는 한글 헤더를 씁니다. 둘 다 받습니다.
FIELDS = {
    'name_ko':      ['bplcnm', '사업장명', '업소명'],
    'road_address': ['rdnwhladdr', '도로명전체주소', '도로명주소'],
    'lot_address':  ['sitewhladdr', '소재지전체주소', '지번주소'],
    'status':       ['dtlstatenm', '상세영업상태명'],
    'category':     ['uptaenm', '업태구분명'],
    'area':         ['faciltotscp', '시설총규모'],
    'permit_date':  ['apvpermymd', '인허가일자'],
    'phone':        ['sitetel', '전화번호', '소재지전화'],
    'x':            ['x', '좌표정보(x)', '좌표정보x'],
    'y':            ['y', '좌표정보(y)', '좌표정보y'],
}

OPEN_STATUSES = {'영업', '영업/정상', '정상'}

# 업태 '한식' 으로 등록되어 있지만 실제로는 주류 업장·카페·타국 음식인 경우가 많습니다.
# 면적 큰 순으로 뽑으면 대형 술집이 대량으로 걸리므로 상호명으로 1차 제외합니다.
# 제외된 항목은 --show-excluded 로 전부 확인할 수 있습니다 (조용히 버리지 않음).
EXCLUDE_KEYWORDS = [
    # 주류 업장
    '펍', 'pub', '맥주', '비어', 'beer', '포차', '호프', '클럽', 'club',
    '라운지', 'lounge', '이자카야', '와인', '칵테일', '위스키', '주점', '술집',
    # 카페·유흥·기타
    '카페', 'cafe', '보드게임', '노래', '피시방', 'pc방', '스터디',
    # 타국 음식
    '마라탕', '훠궈', '짜장', '중화', '스시', '초밥', '라멘', '우동', '돈까스',
    '돈카츠', '카레', '파스타', '피자', '타코', '쌀국수', '베트남', '태국',
    '오마카세', '뷔페',
]

BASE_COLUMNS = [
    'key', 'name', 'name_ko', 'address', 'latitude', 'longitude', 'category',
    'description', 'source_status', 'source_url', 'collected_at', 'collected_by', 'is_active',
]
REVIEW_COLUMNS = ['_keep', '_rank', '_area_m2', '_dist_m', '_permit_year', '_phone', '_lot_address']


def load_env_key(name):
    value = os.environ.get(name)
    if value:
        return value.strip()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line.startswith('#') or '=' not in line:
                continue
            key, _, raw = line.partition('=')
            if key.strip() == name:
                return raw.strip().strip('"').strip("'")
    return None


def fetch_from_api(cache, refresh):
    """서울 열린데이터광장에서 마포구 일반음식점 전량을 받아 캐시한다."""
    if cache.exists() and not refresh:
        records = json.loads(cache.read_text(encoding='utf-8'))
        print(f'캐시 사용: {cache} ({len(records)}건)')
        print('최신 데이터를 받으려면 --refresh 를 쓰세요.\n')
        return records

    key = load_env_key('SEOUL_API_KEY')
    if not key:
        raise SystemExit(
            'SEOUL_API_KEY 를 찾지 못했습니다.\n'
            f'  {ENV_FILE} 에 SEOUL_API_KEY=발급키 를 넣으세요.\n'
            '  (data/.env.example 참고)'
        )

    records, start = [], 1
    total = None
    while total is None or start <= total:
        end = start + API_PAGE_SIZE - 1
        url = f'{SEOUL_API}/{key}/json/{SEOUL_SERVICE}/{start}/{end}/'
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as error:
            raise SystemExit(f'요청 실패 ({start}-{end}): {error}')

        service = payload.get(SEOUL_SERVICE)
        if service is None:
            result = payload.get('RESULT', {})
            raise SystemExit(f'API 오류: {result.get("CODE")} {result.get("MESSAGE")}')

        result = service.get('RESULT', {})
        if result.get('CODE') not in ('INFO-000', None):
            raise SystemExit(f'API 오류 {result.get("CODE")}: {result.get("MESSAGE")}')

        if total is None:
            total = int(service.get('list_total_count', 0))
            print(f'전체 {total}건 수신 시작')
        records.extend(service.get('row', []))
        print(f'  {start}-{min(end, total)} → 누적 {len(records)}건')
        start = end + 1

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(records, ensure_ascii=False), encoding='utf-8')
    print(f'{cache} 에 캐시했습니다.\n')
    return records


def load_records(path):
    """JSON(DATA 배열) 또는 CSV 를 dict 리스트로 읽는다."""
    if path.suffix.lower() == '.json':
        with path.open(encoding='utf-8') as fh:
            payload = json.load(fh)
        if isinstance(payload, dict):
            for key in ('DATA', 'data', 'row'):
                if isinstance(payload.get(key), list):
                    return payload[key]
            raise SystemExit(f'{path.name}: DATA 배열을 찾지 못했습니다 (키: {list(payload)[:5]})')
        if isinstance(payload, list):
            return payload
        raise SystemExit(f'{path.name}: 예상하지 못한 JSON 구조입니다')

    for encoding in ('utf-8-sig', 'cp949', 'utf-8'):
        try:
            with path.open(encoding=encoding, newline='') as fh:
                return list(csv.DictReader(fh))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f'{path.name}: 인코딩을 판별하지 못했습니다')


def build_getter(sample):
    """실제 키 이름을 한 번만 해석해 두고 재사용한다."""
    lookup = {k.replace(' ', '').lower(): k for k in sample}
    resolved = {}
    for role, candidates in FIELDS.items():
        for candidate in candidates:
            actual = lookup.get(candidate.replace(' ', '').lower())
            if actual:
                resolved[role] = actual
                break

    def get(record, role):
        key = resolved.get(role)
        if not key:
            return ''
        value = record.get(key)
        return value.strip() if isinstance(value, str) else ('' if value is None else str(value))

    return get, resolved


def make_converter(epsg):
    try:
        from pyproj import Transformer
    except ImportError:
        raise SystemExit(
            '좌표 변환에 pyproj 가 필요합니다.\n'
            '  pip install pyproj'
        )
    transformer = Transformer.from_crs(f'EPSG:{epsg}', 'EPSG:4326', always_xy=True)

    def convert(x, y):
        try:
            lng, lat = transformer.transform(float(x), float(y))
        except (ValueError, TypeError):
            return None, None
        if not (33 < lat < 39 and 124 < lng < 132):
            return None, None
        return lat, lng

    return convert


def extract(args):
    records = fetch_from_api(args.cache, args.refresh) if args.api else load_records(args.source)
    if not records:
        raise SystemExit('원본에 레코드가 없습니다')

    get, resolved = build_getter(records[0])
    missing = [r for r in ('name_ko', 'status', 'x', 'y', 'area') if r not in resolved]
    if missing:
        raise SystemExit(f'필수 필드를 찾지 못했습니다: {missing}\n실제 키: {list(records[0])[:12]}')

    convert = make_converter(args.epsg)
    stats = {'total': len(records), 'closed': 0, 'category': 0, 'no_coord': 0, 'far': 0, 'keyword': 0}
    keywords = [] if args.no_exclude else EXCLUDE_KEYWORDS
    excluded, rows = [], []

    for record in records:
        if get(record, 'status') not in OPEN_STATUSES:
            stats['closed'] += 1
            continue

        category = get(record, 'category')
        if args.category and args.category not in category:
            stats['category'] += 1
            continue

        name_ko = get(record, 'name_ko')
        hit = next((k for k in keywords if k in name_ko.lower()), None)
        if hit:
            stats['keyword'] += 1
            excluded.append((name_ko, hit))
            continue

        x, y = get(record, 'x'), get(record, 'y')
        if not x or not y:
            stats['no_coord'] += 1
            continue
        lat, lng = convert(x, y)
        if lat is None:
            stats['no_coord'] += 1
            continue

        distance = ((lat - HONGDAE[0]) ** 2 + (lng - HONGDAE[1]) ** 2) ** 0.5 * DEG_TO_M
        if distance > args.radius:
            stats['far'] += 1
            continue

        try:
            area = float(get(record, 'area'))
        except ValueError:
            area = 0.0

        rows.append({
            'key': '',
            'name': '',
            'name_ko': get(record, 'name_ko'),
            'address': get(record, 'road_address') or get(record, 'lot_address'),
            'latitude': round(lat, 6),
            'longitude': round(lng, 6),
            'category': f'Korean - {category}' if category else 'Korean',
            'description': '',
            'source_status': 'public_data',
            'source_url': 'https://www.localdata.go.kr/',
            'collected_at': date.today().isoformat(),
            'collected_by': args.collected_by,
            'is_active': 'true',
            '_keep': '',
            '_rank': 0,
            '_area_m2': area,
            '_dist_m': round(distance),
            '_permit_year': get(record, 'permit_date')[:4],
            '_phone': get(record, 'phone'),
            '_lot_address': get(record, 'lot_address'),
        })

    # 선별 기준: 시설총규모 내림차순 (동점이면 역에 가까운 순)
    rows.sort(key=lambda r: (-r['_area_m2'], r['_dist_m']))
    for index, row in enumerate(rows, start=1):
        row['_rank'] = index

    print(f'전체 {stats["total"]}건')
    print(f'  영업중 아님          -{stats["closed"]}')
    print(f'  업태 불일치          -{stats["category"]}')
    print(f'  상호 키워드 제외      -{stats["keyword"]}')
    print(f'  좌표 없음/변환실패    -{stats["no_coord"]}')
    print(f'  반경 {args.radius:.0f}m 밖       -{stats["far"]}')
    print(f'  → 후보              {len(rows)}곳')

    if args.show_excluded and excluded:
        print(f'\n=== 키워드로 제외된 {len(excluded)}곳 ===')
        for name, keyword in excluded:
            print(f'  [{keyword}] {name}')

    if args.top:
        rows = rows[:args.top]
        print(f'\n면적 상위 {args.top}곳만 출력합니다.')

    if not args.out:
        print('\n--out 을 지정하면 CSV로 저장합니다.')
        return 0

    write_csv(args.out, BASE_COLUMNS + REVIEW_COLUMNS, rows)
    print(f'\n{args.out} 에 {len(rows)}건 저장했습니다.')
    print('\n다음 단계 — 이 파일을 스프레드시트로 열어서:')
    print('  1. 한식이 아닌 곳(중식·일식이 한식으로 등록된 경우)은 _keep 을 비워둡니다')
    print('  2. 남길 곳에 _keep=y, key(영문 slug), name(영문 상호)을 채웁니다')
    print('  3. 승격: filter_localdata.py --promote <이 파일> --out data/curated/restaurants.csv')
    return 0


def promote(args):
    """검토가 끝난 후보 파일에서 _keep=y 행만 골라 restaurants.csv 로 승격."""
    rows = load_records(args.promote)
    kept, problems = [], []

    for index, row in enumerate(rows, start=2):
        if (row.get('_keep') or '').strip().lower() not in ('y', 'yes', 'true', '1'):
            continue
        clean = {c: (row.get(c) or '').strip() for c in BASE_COLUMNS}
        if not clean['key']:
            problems.append(f'{index}행 {clean["name_ko"]}: key 가 비어 있습니다')
        if not clean['name']:
            problems.append(f'{index}행 {clean["name_ko"]}: name(영문) 이 비어 있습니다')
        kept.append(clean)

    print(f'_keep=y 로 표시된 행: {len(kept)}곳')
    if problems:
        print(f'\n✗ 채워지지 않은 항목 {len(problems)}건 — 승격을 중단합니다')
        for problem in problems[:20]:
            print(f'  {problem}')
        if len(problems) > 20:
            print(f'  ... 외 {len(problems) - 20}건')
        return 1

    if not kept:
        print('승격할 행이 없습니다. _keep 컬럼을 확인하세요.')
        return 1

    keys = [r['key'] for r in kept]
    duplicates = {k for k in keys if keys.count(k) > 1}
    if duplicates:
        print(f'\n✗ key 중복: {", ".join(sorted(duplicates))}')
        return 1

    write_csv(args.out, BASE_COLUMNS, kept)
    print(f'{args.out} 에 {len(kept)}곳 저장했습니다.')
    print('이제 validate.py 로 검증하세요.')
    return 0


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description='LOCALDATA → 홍대 MVP 식당 후보')
    parser.add_argument('source', nargs='?', type=Path, help='LOCALDATA 원본 (JSON 또는 CSV)')
    parser.add_argument('--promote', type=Path, help='검토 완료된 후보 CSV 를 restaurants.csv 로 승격')
    parser.add_argument('--out', type=Path, help='출력 CSV 경로')
    parser.add_argument('--category', default='한식', help='업태구분명 필터 (기본: 한식)')
    parser.add_argument('--radius', type=float, default=800, help='홍대입구역 반경 m (기본: 800)')
    parser.add_argument('--top', type=int, help='면적 상위 N곳만 출력')
    parser.add_argument('--epsg', default='5174', help='원본 좌표계 EPSG (기본: 5174)')
    parser.add_argument('--collected-by', default='', help='수집자 이름')
    parser.add_argument('--no-exclude', action='store_true',
                        help='상호 키워드 제외 필터를 끄고 전부 포함')
    parser.add_argument('--show-excluded', action='store_true',
                        help='키워드로 제외된 상호를 전부 출력')
    parser.add_argument('--api', action='store_true',
                        help='정적 파일 대신 서울 열린데이터광장 API 에서 받기 (권장)')
    parser.add_argument('--cache', type=Path, default=API_CACHE, help='API 응답 캐시 경로')
    parser.add_argument('--refresh', action='store_true', help='API 캐시를 무시하고 다시 받기')
    args = parser.parse_args()

    if args.promote:
        if not args.out:
            raise SystemExit('--promote 에는 --out 이 필요합니다')
        return promote(args)

    if not args.api:
        if not args.source:
            parser.error('--api 를 쓰거나 원본 파일 경로를 지정하세요')
        if not args.source.exists():
            raise SystemExit(f'원본 파일이 없습니다: {args.source}')
    return extract(args)


if __name__ == '__main__':
    sys.exit(main())
