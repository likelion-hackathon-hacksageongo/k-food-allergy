#!/usr/bin/env python3
"""
식품안전나라 레시피 DB → 조리 패턴 (통계 집계 방식)

이 DB는 저염·퓨전 건강식 레시피가 섞여 있어서 **개별 레시피를 그대로 "대표 조리
패턴"으로 쓰면 왜곡됩니다.** 그래서 같은 요리군의 레시피 여러 건을 모아 재료
출현 빈도를 계산하고, 그 빈도로 presence 를 결정합니다.

    순두부찌개 4건 → 순두부 4/4(100%) = always
                    멸치   3/4( 75%) = usually
                    곤약   1/4( 25%) = 컷 (개별 레시피의 특이사항)

요리군 정의는 data/mappings/dish_groups.csv 에서 편집합니다.

사용법:

    # 미매칭 재료 빈도 리포트 (별칭 보강용) — 파일 쓰지 않음
    python3 data/scripts/parse_foodsafety.py --report-unmatched

    # 요리군별 집계 결과 확인
    python3 data/scripts/parse_foodsafety.py --dry-run

    # curated CSV 에 병합 (기존 hwpx 패턴은 보존, 같은 key 만 갱신)
    python3 data/scripts/parse_foodsafety.py --merge
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _normalize import KIND_TO_ROLE, is_skippable, load_lookup, match, strip_quantity

DATA_DIR = Path(__file__).resolve().parent.parent
CACHE = DATA_DIR / 'raw' / 'foodsafety_recipes.json'
CURATED = DATA_DIR / 'curated'
MAPPINGS = DATA_DIR / 'mappings'

SOURCE_URL = 'https://openapi.foodsafetykorea.go.kr/'
SOURCE_STATUS = 'public_recipe'

# 재료 텍스트의 섹션 머리말 → pattern_ingredients.role
# 예) '●육수 : 멸치 5g, 다시마 1장' → 이 줄의 재료는 모두 role=broth
SECTION_ROLES = [
    (['육수', '국물', '다시', '스톡'], 'broth'),
    (['양념', '소스', '장', '드레싱', '초장', '겨자'], 'sauce'),
    (['고명', '토핑', '곁들'], 'garnish'),
    (['재료', '주재료', '필수재료', '부재료', '속재료', '반죽', '완자'], 'main'),
]

# presence 판정 임계값 (요리군 내 레시피 중 몇 %에 등장하는가)
PRESENCE_THRESHOLDS = [(0.90, 'always'), (0.60, 'usually'), (0.30, 'sometimes')]

# 표본 수에 따른 확신 상한.
# 비율만 보면 표본이 작을수록 확신이 강해지는 역전이 생깁니다 (2건 중 2건 = 100%).
# 알레르기 판정에서는 과소경고가 과대경고보다 위험하므로, 표본이 적으면
# 상한을 낮춰 약한 판정(=현장 확인 권장)으로 떨어뜨립니다.
CONFIDENCE_CAP = [(5, 'always'), (3, 'usually'), (0, 'sometimes')]
PRESENCE_ORDER = ['sometimes', 'usually', 'always']


def cap_presence(presence, support):
    """표본 수가 뒷받침하지 못하는 강한 판정을 끌어내린다."""
    ceiling = next(level for minimum, level in CONFIDENCE_CAP if support >= minimum)
    if PRESENCE_ORDER.index(presence) <= PRESENCE_ORDER.index(ceiling):
        return presence
    return ceiling


def split_items(line):
    """괄호 밖의 쉼표만 기준으로 자른다.

    '쇠고기(양지 50g, 갈비 50g), 무 30g' 을 그냥 쉼표로 쪼개면
    '쇠고기(양지 50g' / '갈비 50g)' 처럼 깨지므로 괄호 깊이를 추적한다.
    """
    items, buffer, depth = [], [], 0
    for char in line:
        if char in '([{':
            depth += 1
        elif char in ')]}':
            depth = max(0, depth - 1)
        if char in ',、/' and depth == 0:
            items.append(''.join(buffer))
            buffer = []
        else:
            buffer.append(char)
    items.append(''.join(buffer))
    return items


def section_role(header):
    """섹션 머리말에서 role 을 판정. 해당 없으면 None."""
    compact = header.replace(' ', '')
    for keywords, role in SECTION_ROLES:
        if any(keyword in compact for keyword in keywords):
            return role
    return None


def parse_parts(text):
    """RCP_PARTS_DTLS 자유 텍스트 → [(role, 재료명), …]"""
    if not text:
        return []

    body = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    entries, role = [], 'main'

    for raw_line in body.split('\n'):
        line = raw_line.strip().lstrip('-•●▪◦*·[]  ').strip()
        if not line:
            continue

        # '●육수 : 멸치 5g, 다시마 1장' 형태 — 콜론 앞이 섹션명
        if ':' in line:
            header, _, rest = line.partition(':')
            detected = section_role(header)
            if detected and len(header.strip()) <= 12:
                role = detected
                line = rest.strip()
                if not line:
                    continue

        # '재료 닭가슴살(60g), 애호박(30g)' 형태 — 콜론 없이 머리말이 앞에 붙음
        head = line.split()[0] if line.split() else ''
        detected = section_role(head)
        if detected and len(head) <= 6 and head not in ('장',):
            role = detected
            line = line[len(head):].strip()
            if not line:
                continue

        for chunk in split_items(line):
            name = strip_quantity(chunk)
            if not name or is_skippable(name):
                continue
            entries.append((role, name))

    return entries


def load_groups():
    with (MAPPINGS / 'dish_groups.csv').open(encoding='utf-8-sig') as fh:
        return [(r['match_ko'].strip(), r['key'].strip(), r['name_en'].strip())
                for r in csv.DictReader(fh)]


def load_core_ingredients():
    """요리 정의상 반드시 들어가는 재료 (통계 결과보다 우선)."""
    path = MAPPINGS / 'dish_core_ingredients.csv'
    if not path.exists():
        return {}
    lines = [l for l in path.read_text(encoding='utf-8').splitlines()
             if l.strip() and not l.startswith('#')]
    core = defaultdict(dict)
    for row in csv.DictReader(lines):
        core[row['pattern_key'].strip()][row['ingredient_key'].strip()] = row['role'].strip()
    return core


def presence_for(ratio):
    for threshold, value in PRESENCE_THRESHOLDS:
        if ratio >= threshold:
            return value
    return None


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
    parser = argparse.ArgumentParser(description='식품안전나라 레시피 → 조리 패턴')
    parser.add_argument('--source', type=Path, default=CACHE, help='수집 캐시 JSON')
    parser.add_argument('--report-unmatched', action='store_true',
                        help='미매칭 재료를 빈도순으로 출력 (별칭 보강용)')
    parser.add_argument('--dry-run', action='store_true', help='집계 결과만 보고 파일은 쓰지 않음')
    parser.add_argument('--merge', action='store_true', help='curated CSV 에 병합')
    parser.add_argument('--min-support', type=int, default=2,
                        help='요리군당 최소 레시피 수 (기본: 2)')
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f'수집 캐시가 없습니다: {args.source}\n'
                         '  python3 data/scripts/fetch_foodsafety.py 를 먼저 실행하세요.')

    recipes = json.loads(args.source.read_text(encoding='utf-8'))
    aliases, kinds = load_lookup()

    unmatched = Counter()
    matched_total = parsed_total = 0
    # group_key → {ingredient_key: (등장 레시피 수, role Counter)}
    groups = load_groups()
    tally = defaultdict(lambda: defaultdict(lambda: [0, Counter()]))
    support = Counter()
    group_examples = defaultdict(list)

    # 목표 요리군에 속한 레시피의 매칭률이 실제로 중요한 지표입니다.
    # 코퍼스 전체에는 우리 서비스와 무관한 서양 허브·베이킹 재료가 많이 섞여 있습니다.
    in_group_matched = in_group_total = 0
    in_group_unmatched = Counter()

    for recipe in recipes:
        name = (recipe.get('RCP_NM') or '').strip()
        entries = parse_parts(recipe.get('RCP_PARTS_DTLS') or '')
        group_key = next((k for m, k, _n in groups if m in name), None)

        seen_keys = {}
        for role, ingredient in entries:
            parsed_total += 1
            key = match(ingredient, aliases)
            if group_key:
                in_group_total += 1
            if not key:
                unmatched[ingredient] += 1
                if group_key:
                    in_group_unmatched[ingredient] += 1
                continue
            matched_total += 1
            if group_key:
                in_group_matched += 1
            seen_keys.setdefault(key, role)

        if group_key:
            support[group_key] += 1
            group_examples[group_key].append(name)
            for key, role in seen_keys.items():
                entry = tally[group_key][key]
                entry[0] += 1
                entry[1][role] += 1

    rate = 100 * matched_total / parsed_total if parsed_total else 0
    group_rate = 100 * in_group_matched / in_group_total if in_group_total else 0
    print(f'레시피 {len(recipes)}건에서 재료 등장 {parsed_total}건')
    print(f'  코퍼스 전체 매칭   {matched_total}건 ({rate:.1f}%)  미매칭 {len(unmatched)}종')
    print(f'  목표 요리군 매칭   {in_group_matched}/{in_group_total}건 ({group_rate:.1f}%)'
          f'  미매칭 {len(in_group_unmatched)}종   ← 실제로 중요한 지표')

    if args.report_unmatched:
        print(f'\n=== 목표 요리군 내 미매칭 (빈도순, 우선 보강 대상) ===')
        for ingredient, count in in_group_unmatched.most_common(40):
            print(f'  {count:>4}회  {ingredient}')
        print(f'\n=== 코퍼스 전체 미매칭 상위 25종 ===')
        for ingredient, count in unmatched.most_common(25):
            print(f'  {count:>4}회  {ingredient}')
        return 0

    name_en = {k: n for _m, k, n in groups}
    name_ko = {k: m for m, k, _n in groups}

    core = load_core_ingredients()
    forced = 0
    patterns, pattern_ingredients, dropped = [], [], []
    for group_key in sorted(tally, key=lambda g: -support[g]):
        count = support[group_key]
        if count < args.min_support:
            dropped.append((group_key, count))
            continue

        members, seen = [], set()
        # 정의상 재료를 먼저 넣습니다 — 통계 결과가 놓쳐도 반드시 포함되어야 합니다.
        for key, role in core.get(group_key, {}).items():
            if key not in kinds:
                print(f'⚠ dish_core_ingredients: "{key}" 가 ingredients.csv 에 없습니다')
                continue
            seen.add(key)
            forced += 1
            members.append({
                'pattern_key': group_key,
                'ingredient_key': key,
                'presence': 'always',
                'role': role,
            })

        for key, (hits, roles) in tally[group_key].items():
            if key in seen:
                continue
            presence = presence_for(hits / count)
            if not presence:
                continue
            members.append({
                'pattern_key': group_key,
                'ingredient_key': key,
                'presence': cap_presence(presence, count),
                'role': roles.most_common(1)[0][0],
            })
        if not members:
            dropped.append((group_key, count))
            continue

        note = f'식품안전나라 레시피 {count}건 통계 집계'
        if count < 3:
            note += ' (표본 부족 — 검토 필요)'
        patterns.append({
            'key': group_key,
            'name_ko': name_ko[group_key],
            'name_en': name_en[group_key],
            'description': note,
            'source_status': SOURCE_STATUS,
            'source_url': SOURCE_URL,
        })
        pattern_ingredients.extend(members)

    print(f'\n요리군 {len(patterns)}종, 패턴-재료 관계 {len(pattern_ingredients)}건'
          f' (정의상 재료 강제 포함 {forced}건)')
    if dropped:
        print(f'표본 부족으로 제외 {len(dropped)}종: ' +
              ', '.join(f'{name_ko.get(k, k)}({c}건)' for k, c in dropped))

    print(f'\n{"요리군":<12} {"표본":>4} {"재료":>4}  presence 분포')
    print('-' * 62)
    for pattern in patterns:
        key = pattern['key']
        members = [m for m in pattern_ingredients if m['pattern_key'] == key]
        counts = Counter(m['presence'] for m in members)
        listed = ' '.join(f'{p}={counts[p]}' for p in ('always', 'usually', 'sometimes') if counts[p])
        print(f'{pattern["name_ko"]:<12} {support[key]:>4} {len(members):>4}  {listed}')

    if args.dry_run:
        print('\n--dry-run 이므로 파일을 쓰지 않았습니다.')
        return 0
    if not args.merge:
        print('\n--merge 를 주면 curated CSV 에 병합합니다.')
        return 0

    keys = {p['key'] for p in patterns}
    pattern_path = CURATED / 'dish_patterns.csv'
    ingredient_path = CURATED / 'pattern_ingredients.csv'

    kept_patterns = [r for r in read_csv(pattern_path) if r['key'] not in keys]
    kept_ingredients = [r for r in read_csv(ingredient_path) if r['pattern_key'] not in keys]

    write_csv(pattern_path, ['key', 'name_ko', 'name_en', 'description',
                             'source_status', 'source_url'], kept_patterns + patterns)
    write_csv(ingredient_path, ['pattern_key', 'ingredient_key', 'presence', 'role'],
              kept_ingredients + pattern_ingredients)

    print(f'\n{pattern_path} ← 기존 {len(kept_patterns)} + 신규 {len(patterns)}')
    print(f'{ingredient_path} ← 기존 {len(kept_ingredients)} + 신규 {len(pattern_ingredients)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
