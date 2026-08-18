#!/usr/bin/env python3
"""
식당 메뉴명 → 조리 패턴 매칭 검증.

메뉴명을 보유 패턴에 대조해 "우리 DB만으로 판정 가능한가"를 기계적으로 판단합니다.
사람이나 AI 의 해석이 끼어들지 않도록 규칙을 고정했습니다.

판정 규칙
    ✅ PASS    메뉴명이 패턴명과 정확히 일치하거나,
               패턴명으로 끝나고 앞의 수식어가 전부 우리 재료로 해석되는 경우
                 치즈닭갈비 → 닭갈비 패턴 + 치즈(재료)
                 바지락 칼국수 → 칼국수 패턴 + 바지락(재료)
    ◐ REVIEW  패턴명으로 끝나지만 수식어를 해석할 수 없는 경우
                 중화 비빔 칼국수 → '중화'를 재료로 볼 수 없음
    ❌ FAIL    맞는 패턴이 없거나, 패턴이 공개 출처가 아닌 경우(AI 초안)

한국어 합성 요리명은 뒤에 오는 말이 요리 종류이고 앞은 수식어라는 규칙을 씁니다.
수식어가 우리 재료 사전에 있으면 메뉴명 자체가 근거이므로 해석이 필요 없습니다.

    python3 data/scripts/match_menus.py data/review/menu_input.txt
    python3 data/scripts/match_menus.py <파일> --allow-source cooking_pattern
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _normalize import is_skippable, load_lookup, match

DATA_DIR = Path(__file__).resolve().parent.parent
CURATED = DATA_DIR / 'curated'


def read_csv(name):
    with (CURATED / name).open(encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


def parse_input(path):
    """'# 식당명' 다음 줄들을 메뉴로 읽는다."""
    groups, current = [], None
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip().lstrip('-').strip()
        if not line:
            continue
        if line.startswith('#'):
            current = (line.lstrip('#').strip(), [])
            groups.append(current)
        elif current:
            current[1].append(line)
    return groups


# 요리 종류가 아니라 제공 형태를 나타내는 말. 떼어내고 매칭한다.
# '보쌈정식' 은 보쌈에 밥·반찬이 딸려 나온다는 뜻이지 다른 요리가 아니다.
SERVING_SUFFIXES = ['정식', '세트', '한상', '백반', '특', '소', '중', '대',
                    '1인분', '2인분', '(소)', '(중)', '(대)']


def strip_serving(compact):
    for suffix in SERVING_SUFFIXES:
        if compact.endswith(suffix) and len(compact) > len(suffix) + 1:
            return compact[:-len(suffix)]
    return compact


def analyze(menu, patterns, aliases, allowed_sources, restaurant=''):
    """(판정, 패턴, 추가재료 [(key, 표기)], 미해석 토큰) 을 돌려준다."""
    compact = menu.replace(' ', '')

    exact = patterns.get(compact) or patterns.get(strip_serving(compact))
    if exact:
        if exact['source_status'] not in allowed_sources:
            return 'FAIL', exact, [], [f'출처 {exact["source_status"]}']
        return 'PASS', exact, [], []

    # 패턴명으로 끝나는 것 중 가장 긴 것을 요리 종류로 본다
    base = strip_serving(compact)
    tails = [p for name, p in patterns.items()
             if len(name) >= 2 and base.endswith(name) and len(name) < len(base)]
    if not tails:
        return 'FAIL', None, [], []
    pattern = max(tails, key=lambda p: len(p['name_ko'].replace(' ', '')))

    if pattern['source_status'] not in allowed_sources:
        return 'FAIL', pattern, [], [f'출처 {pattern["source_status"]}']

    tail = pattern['name_ko'].replace(' ', '')
    head = base[:-len(tail)]

    # 수식어를 토큰으로 나눠 전부 재료로 해석되는지 본다
    tokens = [t for t in menu.replace(pattern['name_ko'], ' ').split() if t.strip()]
    if not tokens:
        tokens = [head] if head else []

    # 상호명에서 온 토큰은 재료가 아니다 ('녹원쌈밥' 의 '녹원').
    # 단, 메뉴명 전체가 상호명 안에 들어갈 때만 적용한다.
    # '육전국밥' 이라는 상호 때문에 '육전 소고기국밥' 의 육전(재료)까지
    # 브랜드명으로 오인하면 계란·밀 알레르겐을 놓친다.
    shop = restaurant.replace(' ', '')
    brand_ok = compact in shop

    extras, unresolved = [], []
    for token in tokens:
        if is_skippable(token) or strip_serving(token) in SERVING_SUFFIXES:
            continue
        if brand_ok and token and token in shop:
            continue
        key = match(token, aliases)
        if key:
            extras.append((key, token))
        else:
            unresolved.append(token)

    if unresolved:
        return 'REVIEW', pattern, extras, unresolved
    return 'PASS', pattern, extras, []


def main():
    parser = argparse.ArgumentParser(description='메뉴명 → 패턴 매칭 검증')
    parser.add_argument('source', type=Path, help='식당·메뉴 목록 텍스트 파일')
    parser.add_argument('--allow-source', nargs='*', default=['public_recipe'],
                        help='허용할 패턴 출처 (기본: public_recipe 만)')
    parser.add_argument('--min-pass', type=int, default=2,
                        help='식당을 채택할 최소 통과 메뉴 수 (기본: 2)')
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f'입력 파일이 없습니다: {args.source}')

    aliases, _kinds = load_lookup()
    patterns = {r['name_ko'].replace(' ', ''): r for r in read_csv('dish_patterns.csv')}
    allowed = set(args.allow_source)

    print(f'보유 패턴 {len(patterns)}종 · 허용 출처 {", ".join(sorted(allowed))}\n')
    accepted, rejected = [], []

    for restaurant, menus in parse_input(args.source):
        results = [(m,) + analyze(m, patterns, aliases, allowed, restaurant)
                   for m in menus]
        passed = [r for r in results if r[1] == 'PASS']
        mark = '채택' if len(passed) >= args.min_pass else '제외'
        (accepted if len(passed) >= args.min_pass else rejected).append((restaurant, results))

        print(f'[{mark}] {restaurant}  —  통과 {len(passed)}/{len(results)}')
        for menu, verdict, pattern, extras, unresolved in results:
            icon = {'PASS': '✅', 'REVIEW': '◐', 'FAIL': '❌'}[verdict]
            detail = ''
            if pattern:
                detail = f'→ {pattern["key"]}'
                if extras:
                    detail += ' + ' + ', '.join(f'{t}({k})' for k, t in extras)
            if unresolved:
                detail += f'   미해석: {", ".join(unresolved)}'
            print(f'    {icon} {menu:<18} {detail}')
        print()

    print(f'채택 {len(accepted)}곳 / 제외 {len(rejected)}곳')
    total_pass = sum(1 for _r, rs in accepted for x in rs if x[1] == 'PASS')
    print(f'채택 식당의 통과 메뉴 {total_pass}개')
    return 0


if __name__ == '__main__':
    sys.exit(main())
