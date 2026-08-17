"""
재료명 정규화 · 별칭 매칭 공용 모듈.

parse_hwpx.py(표 구조 원재료)와 parse_foodsafety.py(자유 텍스트 재료)가
같은 규칙으로 ingredient_key 를 찾도록 한 곳에 모아둡니다.
표준 라이브러리만 사용합니다.
"""

import csv
import re
from pathlib import Path

CURATED = Path(__file__).resolve().parent.parent / 'curated'

# '다진 마늘' → '마늘' 처럼 앞에 붙는 조리 상태 수식어
PREP_PREFIXES = ['다진', '채썬', '채 썬', '어슷썬', '어슷 썬', '송송 썬', '편', '불린',
                 '삶은', '데친', '볶은', '구운', '썬', '간', '으깬', '마른', '건', '생',
                 '깐', '손질한', '저염', '통조림']

# '잔멸치 볶음' 처럼 뒤에 붙는 조리법
PREP_SUFFIXES = ['볶음', '무침', '조림', '구이', '찜', '절임', '튀김', '숙회', '살']

# 분량 표기에 쓰이는 단위
UNITS = ('g', 'kg', 'mg', 'ml', 'l', 'cc', '개', '장', '모', '마리', '컵', '큰술',
         '작은술', 't', 'T', '줌', '봉지', '뿌리', '알', '판', '쪽', '톨', '대', '줄',
         '포기', '송이', '가닥', '조각', '公', '인분')

_QUANTITY_TAIL = re.compile(
    r'\s*[\d./½¼¾⅓⅔~-]+\s*(?:' + '|'.join(UNITS) + r')?\s*$', re.I)
_LEADING_MARKER = re.compile(r'^[\s\-•●▪◦*·]+')
_AMOUNT_WORDS = ('적당량', '약간', '조금', '취향껏', '기호에 따라')

# 원재료가 아닌 항목 (알레르겐과 무관하거나 표 구조상 잡히는 잡음)
SKIP_VALUES = {
    '-', '', 'ㅍ', 'g', 'oz', 'lb', '원재료', '원산지', '등급', '부위',
    '준비 상태', '식재료 보관 상태', '성분 상세 표기',
    '물', '정수', '얼음', '밥물', '생수', '뜨거운물', '찬물', '적당량', '약간', '육수', '국물', '재료', '꼬치', '무명실', '이쑤시개', '양념', '양념장', '소스',
}

# 재료 kind → pattern_ingredients.role
KIND_TO_ROLE = {
    'jang': 'sauce',
    'sauce': 'sauce',
    'broth': 'broth',
    'garnish': 'garnish',
    'ingredient': 'main',
}


def load_lookup():
    """별칭 → ingredient_key 사전과 ingredient_key → kind 사전을 읽어온다."""
    aliases = {}
    with (CURATED / 'ingredient_aliases.csv').open(encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            alias = (row['alias'] or '').strip().replace(' ', '')
            if alias:
                aliases[alias] = row['ingredient_key'].strip()

    kinds = {}
    with (CURATED / 'ingredients.csv').open(encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            key = row['key'].strip()
            kinds[key] = row['kind'].strip()
            aliases.setdefault((row['name_ko'] or '').strip().replace(' ', ''), key)
    return aliases, kinds


def strip_quantity(text):
    """'연두부 75g(3/4모)' → '연두부', '두부(50g)' → '두부', '소금적당량' → '소금'."""
    name = re.sub(r'<[^>]+>', ' ', text)
    name = re.sub(r'\([^)]*\)', ' ', name)          # 괄호 안 분량·부위 주석
    name = re.sub(r'\[[^\]]*\]', ' ', name)
    name = _LEADING_MARKER.sub('', name)
    for word in _AMOUNT_WORDS:
        name = name.replace(word, ' ')
    name = re.sub(r'\s+', ' ', name).strip()
    # 뒤에 남은 분량을 반복 제거: '케찹 5g 10g' → '케찹'
    for _ in range(3):
        stripped = _QUANTITY_TAIL.sub('', name).strip()
        if stripped == name:
            break
        name = stripped
    return name.strip(' ,.:·')


def candidates(name):
    """조리 수식어를 떼어낸 매칭 후보들을 우선순위 순으로 돌려준다."""
    found, seen = [], set()

    def add(value):
        for form in (value, value.replace(' ', '')):
            form = form.strip()
            if form and form not in seen:
                seen.add(form)
                found.append(form)

    add(name)
    compact = name.replace(' ', '')
    for prefix in PREP_PREFIXES:
        for base in (name, compact):
            if base.startswith(prefix) and len(base) > len(prefix):
                add(base[len(prefix):].strip())
    for suffix in PREP_SUFFIXES:
        for base in (name, compact):
            if base.endswith(suffix) and len(base) > len(suffix):
                add(base[:-len(suffix)].strip())
    without_paren = re.sub(r'\([^)]*\)', '', name).strip()
    if without_paren:
        add(without_paren)
    return found


def match(name, aliases):
    """재료명을 ingredient_key 로 해석한다. 못 찾으면 None."""
    for candidate in candidates(name):
        key = aliases.get(candidate)
        if key:
            return key
    return None


def is_skippable(name):
    # 길이로 걸러내면 안 됩니다 — '무', '배', '밤', '팥', '조', '깨' 는 모두 실제 재료입니다.
    return not name or name in SKIP_VALUES or name.startswith('분량')
