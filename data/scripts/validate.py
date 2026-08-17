#!/usr/bin/env python3
"""
curated/ CSV 검증기.

수집 작업 중 수시로 돌려서 오타·미매칭·중복을 잡습니다.
Django 없이 표준 라이브러리만으로 동작합니다.

    python3 data/scripts/validate.py
    python3 data/scripts/validate.py --quiet    # 오류만 출력

알레르겐 16종은 backend/profiles/models.py 의 AllergenChoice 에서 직접 읽어옵니다
(백엔드가 종류를 늘리면 여기도 자동으로 따라감).
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent
CURATED = DATA_DIR / 'curated'
MAPPINGS = DATA_DIR / 'mappings'
ALLERGEN_MODEL = DATA_DIR.parent / 'backend' / 'profiles' / 'models.py'

FALLBACK_ALLERGENS = {
    'shellfish', 'nuts', 'wheat', 'soy', 'egg', 'dairy', 'fish', 'mollusk',
    'peach', 'peanut', 'pork', 'beef', 'chicken', 'sulfites', 'buckwheat', 'tomato',
}

SOURCE_STATUS = {
    'official_menu', 'public_data', 'public_recipe',
    'cooking_pattern', 'user_feedback', 'unverified',
}
LIKELIHOOD = {'confirmed', 'likely', 'possible', 'none'}
PRESENCE = {'always', 'usually', 'sometimes', 'optional', 'removable'}
ROLE = {'main', 'broth', 'sauce', 'garnish', 'side'}
KIND = {'ingredient', 'broth', 'sauce', 'jang', 'garnish'}
INFO_LEVEL = {'confirmed', 'pattern', 'insufficient'}
BOOLEAN = {'true', 'false', ''}

SLUG_RE = re.compile(r'^[a-z0-9_]+$')

# 홍대입구역 기준 대략적인 MVP 범위. 벗어나면 경고만 냅니다.
HONGDAE = (37.5570, 126.9240)
HONGDAE_RADIUS_DEG = 0.02  # 약 2km


def load_allergen_keys():
    """backend/profiles/models.py 의 AllergenChoice 에서 키 목록을 읽어온다."""
    try:
        text = ALLERGEN_MODEL.read_text(encoding='utf-8')
    except OSError:
        return FALLBACK_ALLERGENS, 'fallback (models.py 를 읽지 못함)'

    block = re.search(r'class AllergenChoice\b.*?(?=\nclass |\Z)', text, re.S)
    if not block:
        return FALLBACK_ALLERGENS, 'fallback (AllergenChoice 를 찾지 못함)'

    keys = set(re.findall(r"^\s+[A-Z_]+\s*=\s*'([a-z_]+)'", block.group(0), re.M))
    if not keys:
        return FALLBACK_ALLERGENS, 'fallback (키를 파싱하지 못함)'
    return keys, str(ALLERGEN_MODEL.relative_to(DATA_DIR.parent))


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.counts = {}

    def error(self, path, line, msg):
        self.errors.append(f'{path.name}:{line}  {msg}')

    def warn(self, path, line, msg):
        self.warnings.append(f'{path.name}:{line}  {msg}')


def read_csv(path, report, required_columns):
    """헤더를 검증하고 (row, line_number) 를 순회한다. 파일이 없으면 빈 리스트."""
    if not path.exists():
        report.errors.append(f'{path.name}  파일이 없습니다')
        return []

    with path.open(encoding='utf-8-sig', newline='') as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            report.errors.append(f'{path.name}  헤더 행이 없습니다')
            return []

        missing = [c for c in required_columns if c not in reader.fieldnames]
        if missing:
            report.errors.append(f'{path.name}  필수 컬럼 누락: {", ".join(missing)}')
            return []

        rows = []
        for line, row in enumerate(reader, start=2):
            if not any((v or '').strip() for v in row.values()):
                continue  # 스프레드시트가 남기는 빈 행
            rows.append((line, {k: (v or '').strip() for k, v in row.items()}))
        report.counts[path.name] = len(rows)
        return rows


def check_required(report, path, line, row, fields):
    for field in fields:
        if not row.get(field):
            report.error(path, line, f'{field} 가 비어 있습니다')


def check_enum(report, path, line, row, field, allowed, required=True):
    value = row.get(field, '')
    if not value:
        if required:
            report.error(path, line, f'{field} 가 비어 있습니다')
        return
    if value not in allowed:
        report.error(path, line, f'{field}="{value}" 는 허용되지 않는 값입니다')


def check_slug(report, path, line, value, field):
    if value and not SLUG_RE.match(value):
        report.error(path, line, f'{field}="{value}" 는 소문자·숫자·밑줄만 사용해야 합니다')


def check_date(report, path, line, row, field):
    value = row.get(field, '')
    if not value:
        report.error(path, line, f'{field} 가 비어 있습니다')
        return
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        report.error(path, line, f'{field}="{value}" 는 YYYY-MM-DD 형식이어야 합니다')


def validate(report, allergens):
    # ---------- ingredients ----------
    path = CURATED / 'ingredients.csv'
    ingredient_keys = set()
    rows = read_csv(path, report, ['key', 'name_ko', 'name_en', 'kind'])
    for line, row in rows:
        check_required(report, path, line, row, ['key', 'name_ko', 'name_en'])
        check_slug(report, path, line, row['key'], 'key')
        check_enum(report, path, line, row, 'kind', KIND)
        if row['key'] in ingredient_keys:
            report.error(path, line, f'key="{row["key"]}" 가 중복됩니다')
        ingredient_keys.add(row['key'])

    # ---------- ingredient_allergens ----------
    path = CURATED / 'ingredient_allergens.csv'
    seen = set()
    rows = read_csv(path, report, ['ingredient_key', 'allergen_key', 'likelihood', 'source_status'])
    for line, row in rows:
        key = row['ingredient_key']
        if key and key not in ingredient_keys:
            report.error(path, line, f'ingredient_key="{key}" 가 ingredients.csv 에 없습니다')
        if row['allergen_key'] and row['allergen_key'] not in allergens:
            report.error(path, line, f'allergen_key="{row["allergen_key"]}" 는 허용된 16종이 아닙니다')
        check_enum(report, path, line, row, 'likelihood', LIKELIHOOD)
        check_enum(report, path, line, row, 'source_status', SOURCE_STATUS)
        pair = (key, row['allergen_key'])
        if pair in seen:
            report.error(path, line, f'{pair} 조합이 중복됩니다')
        seen.add(pair)

    # ---------- ingredient_aliases ----------
    path = CURATED / 'ingredient_aliases.csv'
    aliases = {}
    rows = read_csv(path, report, ['ingredient_key', 'alias'])
    for line, row in rows:
        key, alias = row['ingredient_key'], row['alias']
        if key and key not in ingredient_keys:
            report.error(path, line, f'ingredient_key="{key}" 가 ingredients.csv 에 없습니다')
        if not alias:
            report.error(path, line, 'alias 가 비어 있습니다')
            continue
        normalized = alias.replace(' ', '')
        if normalized in aliases:
            report.error(path, line, f'alias="{alias}" 가 이미 {aliases[normalized]} 에 등록되어 있습니다')
        aliases[normalized] = key

    # 대표 표기가 별칭으로 등록되어 있는지 (레시피 매칭 누락 방지)
    for line, row in read_csv(CURATED / 'ingredients.csv', Report(), ['key', 'name_ko']):
        if row['name_ko'].replace(' ', '') not in aliases:
            report.warn(
                CURATED / 'ingredient_aliases.csv', line,
                f'"{row["name_ko"]}" ({row["key"]}) 가 별칭으로 등록되어 있지 않습니다',
            )

    # ---------- dish_patterns ----------
    path = CURATED / 'dish_patterns.csv'
    pattern_keys = set()
    rows = read_csv(path, report, ['key', 'name_ko', 'name_en', 'source_status'])
    for line, row in rows:
        check_required(report, path, line, row, ['key', 'name_ko', 'name_en'])
        check_slug(report, path, line, row['key'], 'key')
        check_enum(report, path, line, row, 'source_status', SOURCE_STATUS)
        if row['key'] in pattern_keys:
            report.error(path, line, f'key="{row["key"]}" 가 중복됩니다')
        pattern_keys.add(row['key'])

    # ---------- pattern_ingredients ----------
    path = CURATED / 'pattern_ingredients.csv'
    rows = read_csv(path, report, ['pattern_key', 'ingredient_key', 'presence', 'role'])
    for line, row in rows:
        if row['pattern_key'] and row['pattern_key'] not in pattern_keys:
            report.error(path, line, f'pattern_key="{row["pattern_key"]}" 가 dish_patterns.csv 에 없습니다')
        if row['ingredient_key'] and row['ingredient_key'] not in ingredient_keys:
            report.error(path, line, f'ingredient_key="{row["ingredient_key"]}" 가 ingredients.csv 에 없습니다')
        check_enum(report, path, line, row, 'presence', PRESENCE)
        check_enum(report, path, line, row, 'role', ROLE)

    # ---------- restaurants ----------
    path = CURATED / 'restaurants.csv'
    restaurant_keys = set()
    rows = read_csv(path, report, [
        'key', 'name', 'name_ko', 'address', 'latitude', 'longitude',
        'source_status', 'collected_at',
    ])
    for line, row in rows:
        check_required(report, path, line, row, ['key', 'name', 'name_ko', 'address'])
        check_slug(report, path, line, row['key'], 'key')
        check_enum(report, path, line, row, 'source_status', SOURCE_STATUS)
        check_date(report, path, line, row, 'collected_at')
        check_enum(report, path, line, row, 'is_active', BOOLEAN, required=False)
        if row['key'] in restaurant_keys:
            report.error(path, line, f'key="{row["key"]}" 가 중복됩니다')
        restaurant_keys.add(row['key'])

        try:
            lat, lng = float(row['latitude']), float(row['longitude'])
        except ValueError:
            report.error(path, line, 'latitude/longitude 가 숫자가 아닙니다')
            continue
        if not (33 < lat < 39 and 124 < lng < 132):
            report.error(path, line, f'좌표({lat}, {lng})가 한국 범위를 벗어납니다 — 좌표계 변환을 확인하세요')
        elif abs(lat - HONGDAE[0]) > HONGDAE_RADIUS_DEG or abs(lng - HONGDAE[1]) > HONGDAE_RADIUS_DEG:
            report.warn(path, line, f'{row["key"]} 좌표가 홍대 MVP 범위 밖입니다')

    # ---------- menus ----------
    path = CURATED / 'menus.csv'
    menu_keys = set()
    rows = read_csv(path, report, [
        'restaurant_key', 'key', 'name', 'name_ko',
        'info_level', 'source_status', 'collected_at',
    ])
    for line, row in rows:
        check_required(report, path, line, row, ['restaurant_key', 'key', 'name', 'name_ko'])
        check_slug(report, path, line, row['key'], 'key')
        check_enum(report, path, line, row, 'info_level', INFO_LEVEL)
        check_enum(report, path, line, row, 'source_status', SOURCE_STATUS)
        check_date(report, path, line, row, 'collected_at')

        if row['restaurant_key'] and row['restaurant_key'] not in restaurant_keys:
            report.error(path, line, f'restaurant_key="{row["restaurant_key"]}" 가 restaurants.csv 에 없습니다')
        if row['pattern_key'] and row['pattern_key'] not in pattern_keys:
            report.error(path, line, f'pattern_key="{row["pattern_key"]}" 가 dish_patterns.csv 에 없습니다')
        if not row['pattern_key'] and row['info_level'] != 'insufficient':
            report.warn(path, line, f'{row["key"]}: pattern_key 가 없어 재료를 상속받지 못합니다')

        if row['price_krw']:
            if not row['price_krw'].isdigit():
                report.error(path, line, f'price_krw="{row["price_krw"]}" 는 숫자만 입력해야 합니다 (쉼표·"원" 제거)')

        pair = (row['restaurant_key'], row['key'])
        if pair in menu_keys:
            report.error(path, line, f'{pair} 조합이 중복됩니다')
        menu_keys.add(pair)

    # ---------- menu_ingredients ----------
    path = CURATED / 'menu_ingredients.csv'
    rows = read_csv(path, report, [
        'restaurant_key', 'menu_key', 'ingredient_key', 'presence', 'role', 'source_status',
    ])
    for line, row in rows:
        pair = (row['restaurant_key'], row['menu_key'])
        if row['restaurant_key'] and row['menu_key'] and pair not in menu_keys:
            report.error(path, line, f'{pair} 메뉴가 menus.csv 에 없습니다')
        if row['ingredient_key'] and row['ingredient_key'] not in ingredient_keys:
            report.error(path, line, f'ingredient_key="{row["ingredient_key"]}" 가 ingredients.csv 에 없습니다')
        check_enum(report, path, line, row, 'presence', PRESENCE)
        check_enum(report, path, line, row, 'role', ROLE)
        check_enum(report, path, line, row, 'source_status', SOURCE_STATUS)
        if row.get('action') and row['action'] not in {'add', 'remove'}:
            report.error(path, line, f'action="{row["action"]}" 는 add 또는 remove 여야 합니다')

    # ---------- allergen_map ----------
    path = MAPPINGS / 'allergen_map.csv'
    for line, row in read_csv(path, report, ['public_label', 'allergen_key']):
        if row['allergen_key'] not in allergens:
            report.error(path, line, f'allergen_key="{row["allergen_key"]}" 는 허용된 16종이 아닙니다')

    return ingredient_keys, restaurant_keys, menu_keys


def main():
    parser = argparse.ArgumentParser(description='curated/ CSV 검증')
    parser.add_argument('--quiet', action='store_true', help='오류만 출력')
    args = parser.parse_args()

    allergens, source = load_allergen_keys()
    report = Report()
    validate(report, allergens)

    if not args.quiet:
        print(f'알레르겐 {len(allergens)}종 로드: {source}')
        print()
        print('행 수:')
        for name, count in report.counts.items():
            print(f'  {name:<28} {count:>5}')
        print()

    if report.warnings and not args.quiet:
        print(f'⚠ 경고 {len(report.warnings)}건')
        for warning in report.warnings[:20]:
            print(f'  {warning}')
        if len(report.warnings) > 20:
            print(f'  ... 외 {len(report.warnings) - 20}건')
        print()

    if report.errors:
        print(f'✗ 오류 {len(report.errors)}건')
        for error in report.errors:
            print(f'  {error}')
        return 1

    print('✓ 검증 통과')
    return 0


if __name__ == '__main__':
    sys.exit(main())
