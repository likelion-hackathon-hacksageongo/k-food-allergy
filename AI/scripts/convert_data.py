"""
데이터팀 CSV → AI 서버 JSON 변환 스크립트

data/curated/ 폴더의 CSV 파일들을 AI 서버가 사용하는 JSON 형식으로 변환합니다.

사용법:
    cd AI
    python scripts/convert_data.py

출력:
    AI/data/restaurants_for_ai.json
"""

import csv
import json
from pathlib import Path
from collections import defaultdict

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "curated"
MAPPINGS_DIR = BASE_DIR / "data" / "mappings"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "restaurants_for_ai.json"


def load_csv(filepath: Path) -> list[dict]:
    """CSV 파일을 dict 리스트로 로드 (# 주석 무시)"""
    rows = []
    with open(filepath, encoding="utf-8") as f:
        # 주석 라인 필터링
        lines = [line for line in f if not line.startswith("#")]
        reader = csv.DictReader(lines)
        for row in reader:
            rows.append(row)
    return rows


def load_restaurants() -> dict[str, dict]:
    """restaurants.csv 로드 → {key: restaurant_dict}"""
    rows = load_csv(DATA_DIR / "restaurants.csv")
    restaurants = {}
    for i, row in enumerate(rows, start=1):
        key = row["key"]
        restaurants[key] = {
            "id": i,
            "name": row.get("name", ""),
            "name_ko": row.get("name_ko", ""),
            "category": row.get("category", "한식"),
            "address": row.get("address", ""),
            "latitude": float(row.get("latitude", 0)),
            "longitude": float(row.get("longitude", 0)),
            "menu_items": [],
        }
    return restaurants


def load_menus() -> list[dict]:
    """menus.csv 로드"""
    return load_csv(DATA_DIR / "menus.csv")


def load_ingredients() -> dict[str, list[str]]:
    """
    menu_ingredients.csv 로드
    → {(restaurant_key, menu_key): [ingredient_key, ...]}
    """
    rows = load_csv(DATA_DIR / "menu_ingredients.csv")
    ingredients = defaultdict(list)
    for row in rows:
        rkey = row["restaurant_key"]
        mkey = row["menu_key"]
        ikey = row["ingredient_key"]
        ingredients[(rkey, mkey)].append(ikey)
    return ingredients


def load_dish_core_ingredients() -> dict[str, list[str]]:
    """
    dish_core_ingredients.csv 로드
    → {pattern_key: [ingredient_key, ...]}
    """
    rows = load_csv(MAPPINGS_DIR / "dish_core_ingredients.csv")
    core = defaultdict(list)
    for row in rows:
        core[row["pattern_key"]].append(row["ingredient_key"])
    return core


def convert():
    """CSV 데이터를 AI 서버 JSON 형식으로 변환"""
    print("📦 데이터 변환 시작...")

    # 로드
    restaurants = load_restaurants()
    menus = load_menus()
    ingredients = load_ingredients()
    core_ingredients = load_dish_core_ingredients()

    print(f"   식당: {len(restaurants)}개")
    print(f"   메뉴: {len(menus)}개")

    # 메뉴를 식당에 배정
    menu_id_counter = 1
    for row in menus:
        rkey = row["restaurant_key"]
        mkey = row["key"]

        if rkey not in restaurants:
            continue

        # 재료 목록: 직접 입력 + 패턴 기반
        ingredient_list = ingredients.get((rkey, mkey), [])

        # 패턴 기반 재료 추가
        pattern_key = row.get("pattern_key", "")
        if pattern_key and pattern_key in core_ingredients:
            for core_ing in core_ingredients[pattern_key]:
                if core_ing not in ingredient_list:
                    ingredient_list.append(core_ing)

        menu_item = {
            "id": menu_id_counter,
            "name": row.get("name_ko", row.get("name", "")),
            "description": row.get("description", ""),
            "ingredients": ingredient_list,
        }

        restaurants[rkey]["menu_items"].append(menu_item)
        menu_id_counter += 1

    # menu_items가 없는 식당 제거
    valid_restaurants = [
        r for r in restaurants.values()
        if r["menu_items"]
    ]

    print(f"   유효 식당 (메뉴 있음): {len(valid_restaurants)}개")
    total_menus = sum(len(r["menu_items"]) for r in valid_restaurants)
    print(f"   총 메뉴: {total_menus}개")

    # JSON 출력
    output = {
        "version": "1.0",
        "description": "홍대 일대 한식당 데이터 (AI 분석용)",
        "restaurants": valid_restaurants,
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n✅ 변환 완료: {OUTPUT_FILE}")
    print(f"   식당 {len(valid_restaurants)}개 / 메뉴 {total_menus}개")

    # 미리보기
    print(f"\n📋 미리보기 (첫 번째 식당):")
    first = valid_restaurants[0]
    print(f"   {first['name_ko']} ({first['name']})")
    print(f"   메뉴 {len(first['menu_items'])}개:")
    for m in first["menu_items"][:3]:
        print(f"     - {m['name']} | 재료: {', '.join(m['ingredients'][:5])}...")


if __name__ == "__main__":
    convert()
