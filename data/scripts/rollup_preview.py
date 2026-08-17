#!/usr/bin/env python3
"""
패턴 → 재료 → 알레르겐 롤업 미리보기.

백엔드가 DB에서 계산할 결과를 CSV 단계에서 그대로 시뮬레이션합니다.
데이터를 넣기 전에 "이 요리에 이 알레르겐이 잡히는 게 상식적인가"를 눈으로
확인하는 용도이며, 어떤 재료 때문에 잡혔는지까지 보여줍니다.

    python3 data/scripts/rollup_preview.py                 # 전체 패턴 요약
    python3 data/scripts/rollup_preview.py 비빔밥 순댓국밥    # 특정 요리 상세
    python3 data/scripts/rollup_preview.py --allergen soy   # 특정 알레르겐이 걸리는 요리
"""

import argparse
import csv
import sys
from pathlib import Path

CURATED = Path(__file__).resolve().parent.parent / 'curated'

# 강한 것부터. 한 재료가 여러 경로로 같은 알레르겐을 유발하면 가장 강한 것을 취합니다.
RANK = {'confirmed': 3, 'likely': 2, 'possible': 1, 'unlikely': 0}
BY_RANK = {v: k for k, v in RANK.items()}
SYMBOL = {'confirmed': '●', 'likely': '◐', 'possible': '○', 'unlikely': '·'}

# presence(재료가 그 요리에 들어가는 정도)가 likelihood(그 재료에 알레르겐이 있는 정도)의
# 상한을 정합니다. "가끔 들어가는 재료에 확실히 있는 알레르겐"은 결국 "가능" 수준입니다.
# 백엔드 롤업도 이 규칙을 따라야 합니다.
PRESENCE_CEILING = {
    'always': 'confirmed',
    'usually': 'likely',
    'sometimes': 'possible',
    'optional': 'possible',
    'removable': 'possible',
}

# 재료 목록이 어디서 왔는지도 상한을 정합니다.
# 공표 문서(정밀레시피)에서 온 재료와 사람·AI가 추정해 넣은 재료가 같은 확신으로
# 사용자에게 가면 안 됩니다. SCHEMA.md 가 cooking_pattern 을 "추정"으로 정의하므로
# 추정은 confirmed 에 도달할 수 없습니다.
SOURCE_CEILING = {
    'official_menu':   'confirmed',
    'public_data':     'confirmed',
    'public_recipe':   'confirmed',
    'cooking_pattern': 'likely',
    'user_feedback':   'possible',
    'unverified':      'possible',
}


def combine(presence, likelihood, source_status=None):
    """presence × likelihood × 출처 → 실효 likelihood (가장 약한 쪽).

    세 축 모두 상한이며, 셋 중 가장 낮은 값이 사용자에게 보이는 경고 강도입니다.
    """
    ceilings = [RANK[PRESENCE_CEILING.get(presence, 'possible')], RANK[likelihood]]
    if source_status:
        ceilings.append(RANK[SOURCE_CEILING.get(source_status, 'possible')])
    return BY_RANK[min(ceilings)]


def read(name):
    with (CURATED / name).open(encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def resolve_menu_ingredients(menu, pattern_members, overrides, pattern_source=''):
    """패턴 상속 → menu_ingredients 보정 순으로 최종 재료 구성을 만든다.

    백엔드도 같은 순서로 계산해야 합니다.
      1) pattern_key 가 있으면 그 패턴의 재료를 그대로 물려받음
      2) menu_ingredients 의 action=add 는 덮어쓰기(같은 재료면 presence 교체)
      3) action=remove 는 상속된 재료를 제거
    """
    resolved = {}
    for row in pattern_members.get(menu['pattern_key'], []):
        resolved[row['ingredient_key']] = (row['presence'], row['role'], '패턴', pattern_source)

    for row in overrides.get((menu['restaurant_key'], menu['key']), []):
        action = (row.get('action') or 'add').strip() or 'add'
        if action == 'remove':
            resolved.pop(row['ingredient_key'], None)
        else:
            resolved[row['ingredient_key']] = (row['presence'], row['role'], '보정',
                                               row.get('source_status', ''))
    return resolved


def preview_menus(filter_names):
    restaurants = {r['key']: r for r in read('restaurants.csv')}
    patterns = {r['key']: r for r in read('dish_patterns.csv')}
    menus = read('menus.csv')
    ingredients = {r['key']: r for r in read('ingredients.csv')}

    allergens = {}
    for row in read('ingredient_allergens.csv'):
        allergens.setdefault(row['ingredient_key'], []).append(row)

    pattern_members = {}
    for row in read('pattern_ingredients.csv'):
        pattern_members.setdefault(row['pattern_key'], []).append(row)

    overrides = {}
    for row in read('menu_ingredients.csv'):
        overrides.setdefault((row['restaurant_key'], row['menu_key']), []).append(row)

    if not menus:
        print('menus.csv 가 비어 있습니다.')
        return 0

    for restaurant_key in dict.fromkeys(m['restaurant_key'] for m in menus):
        restaurant = restaurants.get(restaurant_key, {})
        own = [m for m in menus if m['restaurant_key'] == restaurant_key]
        if filter_names and not any(f in restaurant.get('name_ko', '') for f in filter_names):
            continue
        print(f'=== {restaurant.get("name_ko", restaurant_key)} '
              f'({restaurant.get("category", "")}) ===\n')

        for menu in own:
            resolved = resolve_menu_ingredients(
                menu, pattern_members, overrides,
                patterns.get(menu['pattern_key'], {}).get('source_status', ''))
            inherited = sum(1 for v in resolved.values() if v[2] == '패턴')
            adjusted = sum(1 for v in resolved.values() if v[2] == '보정')

            found = {}
            for ingredient_key, (presence, _role, origin, source) in resolved.items():
                for entry in allergens.get(ingredient_key, []):
                    allergen = entry['allergen_key']
                    likelihood = combine(presence, entry['likelihood'], source)
                    name_ko = ingredients.get(ingredient_key, {}).get('name_ko', ingredient_key)
                    label = name_ko if presence == 'always' else f'{name_ko}({presence})'
                    if origin == '보정':
                        label += '*'
                    current = found.get(allergen)
                    if current is None or RANK[likelihood] > RANK[current[0]]:
                        found[allergen] = (likelihood, [label])
                    elif likelihood == current[0]:
                        current[1].append(label)

            pattern_status = patterns.get(menu['pattern_key'], {}).get('source_status', '')
            source = (f'패턴 {menu["pattern_key"]} ({pattern_status})'
                      if menu['pattern_key'] else '패턴 없음')
            print(f'  {menu["name_ko"]}  ({menu["name"]})')
            print(f'    {source} · 재료 {len(resolved)}종 (상속 {inherited} + 보정 {adjusted})'
                  f' · info_level={menu["info_level"]} · 출처={menu["source_status"]}')
            if not found:
                print('    검출된 알레르겐 없음')
            for allergen, (likelihood, causes) in sorted(found.items(),
                                                         key=lambda i: -RANK[i[1][0]]):
                print(f'    {SYMBOL[likelihood]} {allergen:<10} {likelihood:<10} ← {", ".join(causes)}')
            print()
    print('* 표시는 menu_ingredients.csv 로 보정한 재료입니다.')
    return 0


def main():
    parser = argparse.ArgumentParser(description='패턴 알레르겐 롤업 미리보기')
    parser.add_argument('dishes', nargs='*', help='상세를 볼 요리명 (한글)')
    parser.add_argument('--allergen', help='이 알레르겐이 걸리는 요리만 출력')
    parser.add_argument('--menus', action='store_true',
                        help='실제 식당 메뉴 단위로 롤업 (패턴 상속 + menu_ingredients 보정)')
    args = parser.parse_args()

    if args.menus:
        return preview_menus(args.dishes)

    patterns = {r['key']: r for r in read('dish_patterns.csv')}
    ingredients = {r['key']: r for r in read('ingredients.csv')}
    pattern_source = {k: p.get('source_status', '') for k, p in patterns.items()}

    allergens = {}
    for row in read('ingredient_allergens.csv'):
        allergens.setdefault(row['ingredient_key'], []).append(row)

    members = {}
    for row in read('pattern_ingredients.csv'):
        members.setdefault(row['pattern_key'], []).append(row)

    # pattern_key → {allergen_key: (likelihood, [원인 재료 …])}
    rolled = {}
    for key, rows in members.items():
        found = {}
        for row in rows:
            ingredient_key = row['ingredient_key']
            for entry in allergens.get(ingredient_key, []):
                allergen = entry['allergen_key']
                likelihood = combine(row['presence'], entry['likelihood'],
                                     pattern_source.get(key))
                name_ko = ingredients.get(ingredient_key, {}).get('name_ko', ingredient_key)
                label = f'{name_ko}({row["presence"]})' if row['presence'] != 'always' else name_ko
                current = found.get(allergen)
                if current is None or RANK[likelihood] > RANK[current[0]]:
                    found[allergen] = (likelihood, [label])
                elif likelihood == current[0]:
                    current[1].append(label)
        rolled[key] = found

    by_name = {p['name_ko']: k for k, p in patterns.items()}

    if args.allergen:
        print(f'=== "{args.allergen}" 가 검출되는 요리 ===')
        hits = [(patterns[k]['name_ko'], v[args.allergen])
                for k, v in rolled.items() if args.allergen in v]
        hits.sort(key=lambda h: -RANK[h[1][0]])
        for name, (likelihood, causes) in hits:
            print(f'  {SYMBOL[likelihood]} {likelihood:<10} {name:<12} ← {", ".join(causes)}')
        print(f'\n{len(hits)}/{len(rolled)}종')
        return 0

    targets = args.dishes or []
    if targets:
        for dish in targets:
            key = by_name.get(dish)
            if not key:
                print(f'✗ "{dish}" 패턴이 없습니다')
                continue
            print(f'=== {dish} ({key}) ===')
            print(f'  재료 {len(members.get(key, []))}종')
            for allergen, (likelihood, causes) in sorted(
                    rolled[key].items(), key=lambda i: -RANK[i[1][0]]):
                print(f'  {SYMBOL[likelihood]} {allergen:<10} {likelihood:<10} ← {", ".join(causes)}')
            print()
        return 0

    print(f'{"요리":<16} {"재료":>4}  알레르겐 (● 확정 ◐ 유력 ○ 가능)')
    print('-' * 84)
    for key, pattern in sorted(patterns.items(), key=lambda p: -len(rolled.get(p[0], {}))):
        found = rolled.get(key, {})
        listed = ' '.join(f'{SYMBOL[l]}{a}' for a, (l, _) in
                          sorted(found.items(), key=lambda i: -RANK[i[1][0]]))
        print(f'{pattern["name_ko"]:<16} {len(members.get(key, [])):>4}  {listed}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
