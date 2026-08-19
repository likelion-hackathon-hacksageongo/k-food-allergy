#!/usr/bin/env python3
"""
한식진흥원 정밀레시피(hwpx) → dish_patterns.csv + pattern_ingredients.csv

hwpx 는 ZIP + OWPML(XML) 컨테이너라 표준 라이브러리만으로 파싱됩니다.
첫 번째 표가 원재료 표이며, 셀의 colAddr/colSpan 으로 하위 조리 그룹을 분리합니다.

    colAddr=0, colSpan=2  → 상위 재료 (흰밥, 고추장, 참기름)
    colAddr=0, colSpan=1  → 하위 그룹명 (버섯나물) + colAddr=1 이 그 그룹의 첫 재료
    colAddr=1             → 직전 그룹에 속한 재료

사용법:

    # 미매칭 재료만 확인 (파일 쓰지 않음)
    python3 data/scripts/parse_hwpx.py --dry-run

    # CSV 생성
    python3 data/scripts/parse_hwpx.py \
        --out-patterns data/curated/dish_patterns.csv \
        --out-ingredients data/curated/pattern_ingredients.csv

presence 규칙:
    정밀레시피는 요리 하나의 "표준" 조리법이므로 등재된 재료는 모두 `always` 로 둡니다.
    식당별 예외(야채비빔밥에 소고기 없음 등)는 menu_ingredients.csv 의
    action=remove 로 덮어씁니다.

role 규칙:
    추측하지 않고 ingredients.csv 의 kind 에서 결정합니다.
    jang/sauce → sauce, broth → broth, garnish → garnish, ingredient → main
"""

import argparse
import csv
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _normalize import KIND_TO_ROLE, candidates, is_skippable, load_lookup

NS = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
DATA_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = DATA_DIR / 'raw' / '한식진흥원_한식 정밀레시피'
CURATED = DATA_DIR / 'curated'
MAPPINGS = DATA_DIR / 'mappings'

SOURCE_URL = 'https://www.hansik.or.kr/'

def load_dish_names():
    path = MAPPINGS / 'dish_names.csv'
    if not path.exists():
        return {}
    with path.open(encoding='utf-8-sig') as fh:
        return {r['name_ko'].strip(): (r['key'].strip(), r['name_en'].strip())
                for r in csv.DictReader(fh)}


def cell_text(tc):
    return ' '.join(t.text.strip() for t in tc.iter(NS + 't') if t.text and t.text.strip())


def parse_ingredient_table(path):
    """정밀레시피 hwpx 의 첫 표에서 (그룹명, 재료명, 분량g) 목록을 뽑는다."""
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read('Contents/section0.xml'))

    tables = list(root.iter(NS + 'tbl'))
    if not tables:
        return []

    rows = tables[0].findall(NS + 'tr')
    if not rows:
        return []

    # 표 모드 판별: 헤더의 '원재료' 칸이 2칸을 병합하고 있으면 하위 그룹 열이 있는
    # 구조, 1칸이면 평면 구조. 레시피마다 다르므로 반드시 파일별로 확인해야 한다.
    header_cells = rows[0].findall(NS + 'tc')
    header_span = header_cells[0].find(NS + 'cellSpan') if header_cells else None
    grouped = header_span is not None and int(header_span.get('colSpan')) >= 2

    entries, group = [], None
    for tr in rows:
        cells = tr.findall(NS + 'tc')
        if not cells:
            continue
        texts = [cell_text(tc) for tc in cells]
        addr = cells[0].find(NS + 'cellAddr')
        span = cells[0].find(NS + 'cellSpan')
        col = int(addr.get('colAddr')) if addr is not None else 0
        colspan = int(span.get('colSpan')) if span is not None else 1

        if not grouped:
            if col != 0:
                continue
            name, offset = texts[0], 1          # 평면 구조: 첫 칸이 곧 재료명
        elif col == 0 and colspan >= 2:
            name, offset = texts[0], 1          # 상위 재료 (그룹 없음)
            group = None
        elif col == 0:
            group = texts[0]                    # 하위 그룹 시작
            if len(texts) < 2:
                continue
            name, offset = texts[1], 2
        else:
            name, offset = texts[0], 1          # 직전 그룹에 속한 재료

        name = name.strip()
        if is_skippable(name):
            continue

        # 분량(g)은 재료명 뒤 4번째 칸 (원산지/등급/부위 다음)
        grams = ''
        for value in texts[offset:]:
            if re.fullmatch(r'\d+(\.\d+)?', value.strip()):
                grams = value.strip()
                break
        entries.append((group, name, grams))
    return entries


def main():
    parser = argparse.ArgumentParser(description='정밀레시피 hwpx → 조리 패턴 CSV')
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE, help='hwpx 폴더')
    parser.add_argument('--out-patterns', type=Path, help='dish_patterns.csv 경로')
    parser.add_argument('--out-ingredients', type=Path, help='pattern_ingredients.csv 경로')
    parser.add_argument('--dry-run', action='store_true', help='매칭 결과만 보고 파일은 쓰지 않음')
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f'hwpx 폴더가 없습니다: {args.source}')

    aliases, kinds = load_lookup()
    dish_names = load_dish_names()

    files = sorted(args.source.glob('*.hwpx'))
    if not files:
        raise SystemExit(f'{args.source} 에 hwpx 파일이 없습니다')

    patterns, pattern_ingredients = [], []
    unmatched = Counter()
    unknown_dishes, matched_count, total_count = [], 0, 0

    for path in files:
        # '12. 비빔밥.hwpx' → '비빔밥'
        dish_ko = re.sub(r'^\d+\.\s*', '', path.stem).strip()
        mapping = dish_names.get(dish_ko)
        if not mapping:
            unknown_dishes.append(dish_ko)
            continue
        dish_key, dish_en = mapping

        entries = parse_ingredient_table(path)
        if not entries:
            print(f'⚠ {path.name}: 원재료 표를 찾지 못했습니다')
            continue

        patterns.append({
            'key': dish_key,
            'name_ko': dish_ko,
            'name_en': dish_en,
            'description': f'한식진흥원 정밀레시피 기준 ({len(entries)}종 원재료)',
            'source_status': 'public_recipe',
            'source_url': SOURCE_URL,
        })

        seen_in_dish = set()
        for group, name, _grams in entries:
            total_count += 1
            key = next((aliases[c] for c in candidates(name) if c in aliases), None)
            if not key:
                unmatched[name] += 1
                continue
            matched_count += 1
            if key in seen_in_dish:
                continue                        # 같은 재료가 여러 그룹에 나오면 1회만
            seen_in_dish.add(key)
            pattern_ingredients.append({
                'pattern_key': dish_key,
                'ingredient_key': key,
                'presence': 'always',
                'role': KIND_TO_ROLE.get(kinds.get(key, 'ingredient'), 'main'),
            })

    rate = 100 * matched_count / total_count if total_count else 0
    print(f'레시피 {len(patterns)}종, 원재료 등장 {total_count}건')
    print(f'매칭 {matched_count}건 ({rate:.1f}%), 미매칭 {sum(unmatched.values())}건')
    print(f'패턴-재료 관계 {len(pattern_ingredients)}건')

    if unknown_dishes:
        print(f'\n⚠ dish_names.csv 에 없는 요리 {len(unknown_dishes)}종 (건너뜀):')
        for dish in unknown_dishes:
            print(f'  {dish}')

    if unmatched:
        print(f'\n=== 미매칭 재료 {len(unmatched)}종 (빈도순) ===')
        print('ingredients.csv / ingredient_aliases.csv 에 추가하세요.')
        for name, count in unmatched.most_common():
            print(f'  {count:>3}회  {name}')

    if args.dry_run:
        print('\n--dry-run 이므로 파일을 쓰지 않았습니다.')
        return 0

    keys = {p['key'] for p in patterns}
    if args.out_patterns:
        kept = merge(args.out_patterns, 'key', keys)
        write(args.out_patterns, ['key', 'name_ko', 'name_en', 'description',
                                  'source_status', 'source_url'], kept + patterns)
        print(f'\n{args.out_patterns} ← 기존 {len(kept)} + 이번 {len(patterns)}')
    if args.out_ingredients:
        kept = merge(args.out_ingredients, 'pattern_key', keys)
        write(args.out_ingredients, ['pattern_key', 'ingredient_key', 'presence', 'role'],
              kept + pattern_ingredients)
        print(f'{args.out_ingredients} ← 기존 {len(kept)} + 이번 {len(pattern_ingredients)}')
    return 0


def merge(path, key_field, generated_keys):
    """이번 실행이 생성하는 key 만 교체하고 나머지 행은 보존한다.

    통째로 덮어쓰면 다른 소스(식품안전나라 집계, 손으로 넣은 패턴)의 행이
    날아가므로 반드시 병합해야 한다.
    """
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig') as fh:
        return [r for r in csv.DictReader(fh) if r[key_field] not in generated_keys]


def write(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    sys.exit(main())
