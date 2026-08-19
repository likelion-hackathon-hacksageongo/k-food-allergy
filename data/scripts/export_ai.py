#!/usr/bin/env python3
"""
curated/ CSV → AI 모듈 입력 restaurants.json

AI/DATA_FORMAT.md 가 요구하는 형식으로 내보냅니다. 데이터팀이 CSV 로 관리하고
AI 팀이 JSON 을 받는 구조라, 그 사이를 이 스크립트 하나로 고정합니다.

핵심은 `ingredients` 입니다. AI/DATA_FORMAT.md 4절이 "보이는 재료 + 숨은 재료
(육수·양념·소스)를 모두 기입" 하라고 하는데, 그게 정확히 우리 패턴 상속의 결과물입니다.
메뉴에 pattern_key 만 적혀 있어도 EPIS·정밀레시피에서 온 재료 10~20종이 따라옵니다.

    python3 data/scripts/export_ai.py                  # data/exports/restaurants.json
    python3 data/scripts/export_ai.py --out -          # 표준출력으로
    python3 data/scripts/export_ai.py --include-inactive

재료 구성 순서(패턴 상속 → menu_ingredients 보정)는 rollup_preview.py 의 함수를
그대로 가져다 씁니다. 미리보기와 실제 내보내기가 어긋나면 안 됩니다.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rollup_preview import read, resolve_menu_ingredients

DATA_DIR = Path(__file__).resolve().parent.parent
MAPPINGS = DATA_DIR / 'mappings'
DEFAULT_OUT = DATA_DIR / 'exports' / 'restaurants.json'
DEFAULT_CATEGORY = '한식'

# presence 는 AI 쪽 스키마에 자리가 없습니다(ingredients 가 그냥 list[str]).
# 값을 버리면 "가끔 들어가는 재료"가 "항상 들어가는 재료"로 격상되므로
# 재료명 뒤에 한국어로 붙여 보냅니다. 프롬프트에 그대로 들어가 읽힙니다.
PRESENCE_LABEL = {
    'always': '',
    'usually': '(대개)',
    'sometimes': '(가끔)',
    'optional': '(선택)',
    'removable': '(뺄 수 있음)',
}

# 보이는 재료 먼저, 숨은 재료(육수·양념) 나중. DATA_FORMAT.md 4절의 서술 순서입니다.
ROLE_ORDER = {'main': 0, 'side': 1, 'garnish': 2, 'broth': 3, 'sauce': 4}


def load_category_map(report):
    path = MAPPINGS / 'ai_category_map.csv'
    if not path.exists():
        report.append(f'{path.name} 이 없어 모든 식당을 "{DEFAULT_CATEGORY}" 으로 내보냅니다')
        return {}
    lines = [l for l in path.read_text(encoding='utf-8').splitlines()
             if l.strip() and not l.startswith('#')]
    return {r['category'].strip(): r['ai_category'].strip()
            for r in csv.DictReader(lines)}


def build(include_inactive=False):
    warnings = []
    category_map = load_category_map(warnings)

    restaurants = read('restaurants.csv')
    menus = read('menus.csv')
    ingredients = {r['key']: r for r in read('ingredients.csv')}
    patterns = {r['key']: r for r in read('dish_patterns.csv')}

    pattern_members = {}
    for row in read('pattern_ingredients.csv'):
        pattern_members.setdefault(row['pattern_key'], []).append(row)

    overrides = {}
    for row in read('menu_ingredients.csv'):
        overrides.setdefault((row['restaurant_key'], row['menu_key']), []).append(row)

    exported, skipped = [], []
    for index, restaurant in enumerate(restaurants, start=1):
        if not include_inactive and (restaurant.get('is_active') or 'true').lower() == 'false':
            skipped.append(f'{restaurant["name_ko"]} (is_active=false)')
            continue

        raw_category = (restaurant.get('category') or '').strip()
        category = category_map.get(raw_category)
        if category is None:
            category = DEFAULT_CATEGORY
            if raw_category:
                warnings.append(
                    f'{restaurant["name_ko"]}: category="{raw_category}" 가 '
                    f'ai_category_map.csv 에 없어 "{DEFAULT_CATEGORY}" 으로 내보냅니다')

        items = []
        for order, menu in enumerate(
                [m for m in menus if m['restaurant_key'] == restaurant['key']], start=1):
            resolved = resolve_menu_ingredients(
                menu, pattern_members, overrides,
                patterns.get(menu['pattern_key'], {}).get('source_status', ''))

            listed = []
            for key, (presence, role, _origin, _source) in sorted(
                    resolved.items(), key=lambda kv: ROLE_ORDER.get(kv[1][1], 9)):
                name_ko = ingredients.get(key, {}).get('name_ko', key)
                listed.append(name_ko + PRESENCE_LABEL.get(presence, ''))

            if not listed:
                warnings.append(f'{restaurant["name_ko"]} / {menu["name_ko"]}: '
                                f'재료가 비어 있습니다 (pattern_key 확인 필요)')

            item = {
                'id': index * 100 + order,
                'name': menu['name'],
                'name_ko': menu['name_ko'],
                'description': menu.get('description', ''),
                'ingredients': listed,
                'info_level': menu['info_level'],
                'source_status': menu['source_status'],
            }
            if (menu.get('price_krw') or '').isdigit():
                item['price'] = int(menu['price_krw'])
            items.append(item)

        if not items:
            skipped.append(f'{restaurant["name_ko"]} (메뉴 없음)')
            continue

        exported.append({
            'id': index,
            'name': restaurant['name'],
            'name_ko': restaurant['name_ko'],
            'category': category,
            'address': restaurant['address'],
            'latitude': float(restaurant['latitude']),
            'longitude': float(restaurant['longitude']),
            'menu_items': items,
        })

    return exported, warnings, skipped


def main():
    parser = argparse.ArgumentParser(description='curated/ CSV → AI 입력 restaurants.json')
    parser.add_argument('--out', default=str(DEFAULT_OUT),
                        help='출력 경로 ("-" 면 표준출력)')
    parser.add_argument('--include-inactive', action='store_true',
                        help='is_active=false 인 식당도 포함')
    args = parser.parse_args()

    exported, warnings, skipped = build(args.include_inactive)
    payload = json.dumps(exported, ensure_ascii=False, indent=2) + '\n'

    if args.out == '-':
        sys.stdout.write(payload)
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding='utf-8')

    menu_count = sum(len(r['menu_items']) for r in exported)
    ingredient_count = sum(len(m['ingredients']) for r in exported for m in r['menu_items'])
    print(f'{out} ← 식당 {len(exported)}곳 · 메뉴 {menu_count}개 · 재료 {ingredient_count}건')
    if menu_count:
        print(f'  메뉴당 평균 재료 {ingredient_count / menu_count:.1f}종')
    for line in skipped:
        print(f'  건너뜀: {line}')
    for line in warnings:
        print(f'  ⚠ {line}')

    # AI/schemas/types.py 는 아직 name 을 한국어로 받도록 되어 있습니다
    # (RestaurantInput.name / MenuItemInput.name 의 description 이 "(한국어)").
    # DATA_FORMAT.md 는 name=영문·name_ko=한글로 바뀌었으므로 둘이 어긋납니다.
    # pydantic 이 name_ko 를 extra 로 조용히 버리므로 프롬프트에 영문 메뉴명만 들어갑니다.
    print('\n※ AI/schemas/types.py 가 name_ko 를 받도록 수정되기 전까지는')
    print('  분석 프롬프트에 영문 메뉴명이 들어갑니다. AI 담당자 확인 필요.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
