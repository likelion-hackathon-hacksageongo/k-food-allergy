#!/usr/bin/env python3
"""
EPIS 레시피 API → 조리 패턴 (구조화 데이터 직결)

식품안전나라와 달리 재료가 한 행씩 오고 IRDNT_TY_NM 이 역할을 명시하므로
텍스트 파싱이 필요 없습니다. 요리당 레시피 1건인 정제 데이터라
한식진흥원 정밀레시피와 같은 취급(presence=always)을 합니다.

    IRDNT_TY_NM   주재료·부재료 → role=main
                  양념         → role=sauce

패턴 key 는 요리명을 국어의 로마자 표기법으로 변환해 만듭니다
(감자탕 → gamjatang). 385종을 손으로 매핑할 수 없어 자동 생성하되,
사람이 읽는 식별자는 name_ko 입니다.

같은 요리명이 이미 있으면:
    기존이 cooking_pattern(AI 초안) → EPIS 공개 출처로 교체 (key 유지)
    기존이 public_recipe            → 건너뜀 (중복 방지)

사용법:
    python3 data/scripts/parse_epis.py --report-unmatched   # 별칭 보강용
    python3 data/scripts/parse_epis.py --dry-run
    python3 data/scripts/parse_epis.py --merge
"""

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _normalize import is_skippable, load_lookup, match, strip_quantity

DATA_DIR = Path(__file__).resolve().parent.parent
RAW = DATA_DIR / 'raw'
CURATED = DATA_DIR / 'curated'

SOURCE_URL = 'https://www.data.go.kr/data/15058981/openapi.do'
SOURCE_STATUS = 'public_recipe'

ROLE_BY_TYPE = {'주재료': 'main', '부재료': 'main', '양념': 'sauce'}

# 국어의 로마자 표기법 — 자모 단위 매핑.
# 자음 동화까지는 반영하지 않지만, 결정론적이고 읽을 수 있는 slug 를 만듭니다.
CHOSEONG = ['g', 'kk', 'n', 'd', 'tt', 'r', 'm', 'b', 'pp', 's', 'ss', '',
            'j', 'jj', 'ch', 'k', 't', 'p', 'h']
JUNGSEONG = ['a', 'ae', 'ya', 'yae', 'eo', 'e', 'yeo', 'ye', 'o', 'wa', 'wae',
             'oe', 'yo', 'u', 'wo', 'we', 'wi', 'yu', 'eu', 'ui', 'i']
JONGSEONG = ['', 'k', 'k', 'k', 'n', 'n', 'n', 't', 'l', 'k', 'm', 'l', 'l',
             'l', 'p', 'l', 'm', 'p', 'p', 't', 't', 'ng', 't', 't', 'k',
             't', 'p', 't']


def romanize(text):
    """'감자탕' → 'gamjatang'. 한글이 아닌 문자는 버립니다."""
    out = []
    for char in text:
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            index = code - 0xAC00
            out.append(CHOSEONG[index // 588])
            out.append(JUNGSEONG[(index % 588) // 28])
            out.append(JONGSEONG[index % 28])
        elif char.isalnum():
            out.append(char.lower())
        else:
            out.append('_')
    slug = ''.join(out)
    while '__' in slug:
        slug = slug.replace('__', '_')
    return slug.strip('_') or 'dish'


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def write_csv(path, columns, rows):
    with path.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description='EPIS 레시피 → 조리 패턴')
    parser.add_argument('--report-unmatched', action='store_true',
                        help='미매칭 재료를 빈도순으로 출력')
    parser.add_argument('--dry-run', action='store_true', help='결과만 보고 파일은 쓰지 않음')
    parser.add_argument('--merge', action='store_true', help='curated CSV 에 병합')
    parser.add_argument('--nation', default='한식', help='NATION_NM 필터 (기본: 한식)')
    parser.add_argument('--min-ingredients', type=int, default=3,
                        help='재료가 이보다 적은 레시피는 제외 (기본: 3)')
    args = parser.parse_args()

    recipe_path, ingredient_path = RAW / 'epis_recipes.json', RAW / 'epis_ingredients.json'
    if not recipe_path.exists() or not ingredient_path.exists():
        raise SystemExit('수집 캐시가 없습니다.\n'
                         '  python3 data/scripts/fetch_epis.py --skip-steps 를 먼저 실행하세요.')

    recipes = json.loads(recipe_path.read_text(encoding='utf-8'))
    ingredients = json.loads(ingredient_path.read_text(encoding='utf-8'))
    aliases, kinds = load_lookup()

    wanted = {r['RECIPE_ID']: r for r in recipes
              if not args.nation or r.get('NATION_NM') == args.nation}

    by_recipe = defaultdict(list)
    for row in ingredients:
        if row['RECIPE_ID'] in wanted:
            by_recipe[row['RECIPE_ID']].append(row)

    unmatched = Counter()
    matched_total = seen_total = 0
    resolved = {}   # recipe_id → {ingredient_key: role}

    for recipe_id, rows in by_recipe.items():
        found = {}
        for row in sorted(rows, key=lambda r: r.get('IRDNT_SN', 0)):
            name = strip_quantity(row.get('IRDNT_NM') or '')
            if not name or is_skippable(name):
                continue
            seen_total += 1
            key = match(name, aliases)
            if not key:
                unmatched[name] += 1
                continue
            matched_total += 1
            role = ROLE_BY_TYPE.get((row.get('IRDNT_TY_NM') or '').strip(), 'main')
            # 재료 kind 가 육수·양념이면 그 쪽을 우선 (다시마육수는 양념이 아니라 broth)
            kind = kinds.get(key, 'ingredient')
            if kind == 'broth':
                role = 'broth'
            elif kind in ('jang', 'sauce') and role == 'main':
                role = 'sauce'
            elif kind == 'garnish':
                role = 'garnish'
            found.setdefault(key, role)
        if len(found) >= args.min_ingredients:
            resolved[recipe_id] = found

    rate = 100 * matched_total / seen_total if seen_total else 0
    print(f'{args.nation} 레시피 {len(wanted)}종, 재료 등장 {seen_total}건')
    print(f'  매칭 {matched_total}건 ({rate:.1f}%)  미매칭 {len(unmatched)}종')
    print(f'  재료 {args.min_ingredients}종 이상인 레시피 {len(resolved)}종')

    if args.report_unmatched:
        print(f'\n=== 미매칭 재료 상위 50종 ===')
        for name, count in unmatched.most_common(50):
            print(f'  {count:>3}회  {name}')
        return 0

    # 기존 패턴과 요리명으로 충돌 확인
    existing = read_csv(CURATED / 'dish_patterns.csv')
    by_name = {r['name_ko']: r for r in existing}

    patterns, members, replaced, skipped = [], [], [], []
    used_keys = {r['key'] for r in existing}

    for recipe_id, found in sorted(resolved.items()):
        recipe = wanted[recipe_id]
        name_ko = (recipe.get('RECIPE_NM_KO') or '').strip()
        category = (recipe.get('TY_NM') or '').strip()
        prior = by_name.get(name_ko)

        if prior and prior['source_status'] == SOURCE_STATUS:
            skipped.append(name_ko)
            continue
        if prior:                       # AI 초안 → 공개 출처로 교체, key 는 유지
            key = prior['key']
            replaced.append(f'{name_ko}({key})')
        else:
            key = romanize(name_ko)
            if key in used_keys:
                key = f'{key}_{recipe_id}'
            used_keys.add(key)

        patterns.append({
            'key': key,
            'name_ko': name_ko,
            'name_en': romanize(name_ko).replace('_', ' ').title(),
            'description': f'EPIS 레시피 DB {category} (RECIPE_ID {recipe_id}) · 재료 {len(found)}종',
            'source_status': SOURCE_STATUS,
            'source_url': SOURCE_URL,
        })
        for ingredient_key, role in found.items():
            members.append({
                'pattern_key': key,
                'ingredient_key': ingredient_key,
                'presence': 'always',
                'role': role,
            })

    print(f'\n신규·교체 패턴 {len(patterns)}종, 패턴-재료 {len(members)}건')
    if replaced:
        print(f'  AI 초안 → 공개 출처로 교체 {len(replaced)}종: {", ".join(replaced)}')
    if skipped:
        print(f'  이미 공개 출처로 있어 건너뜀 {len(skipped)}종: {", ".join(skipped[:12])}'
              + (' …' if len(skipped) > 12 else ''))

    counts = Counter(p['description'].split('DB ')[1].split(' (')[0] for p in patterns)
    print('\n분류별 신규 패턴:')
    for name, count in counts.most_common():
        print(f'  {name:<20} {count}')

    if args.dry_run:
        print('\n--dry-run 이므로 파일을 쓰지 않았습니다.')
        return 0
    if not args.merge:
        print('\n--merge 를 주면 curated CSV 에 병합합니다.')
        return 0

    keys = {p['key'] for p in patterns}
    pattern_path = CURATED / 'dish_patterns.csv'
    member_path = CURATED / 'pattern_ingredients.csv'
    kept_p = [r for r in read_csv(pattern_path) if r['key'] not in keys]
    kept_m = [r for r in read_csv(member_path) if r['pattern_key'] not in keys]

    write_csv(pattern_path, ['key', 'name_ko', 'name_en', 'description',
                             'source_status', 'source_url'], kept_p + patterns)
    write_csv(member_path, ['pattern_key', 'ingredient_key', 'presence', 'role'],
              kept_m + members)
    print(f'\n{pattern_path} ← 기존 {len(kept_p)} + 이번 {len(patterns)}')
    print(f'{member_path} ← 기존 {len(kept_m)} + 이번 {len(members)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
