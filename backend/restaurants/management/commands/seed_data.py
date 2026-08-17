from django.core.management.base import BaseCommand
from django.db import transaction

from restaurants.models import Restaurant
from menus.models import MenuItem, MenuAllergen

# Sample data: a handful of Hongdae-area restaurants with menu items and
# allergen tags, for local development / demo purposes.
RESTAURANTS = [
    {
        "name": "Hongdae Sundubu House",
        "name_ko": "홍대 순두부집",
        "address": "서울 마포구 홍익로 12",
        "latitude": 37.5551,
        "longitude": 126.9236,
        "category": "Korean - Stew",
        "description": "Soft tofu stew (sundubu-jjigae) specialist near Hongik Univ.",
        "source_type": "public_menu",
        "menus": [
            {
                "name": "Seafood Sundubu Jjigae",
                "name_ko": "해물 순두부찌개",
                "price": 9000,
                "info_level": "confirmed",
                "allergens": [
                    ("shellfish", "confirmed", "public_menu", "Contains shrimp and clams"),
                    ("mollusk", "confirmed", "public_menu", "Contains clams and squid"),
                    ("soy", "confirmed", "public_menu", "Tofu base"),
                    ("egg", "likely", "cooking_pattern", "Often finished with a raw egg"),
                ],
            },
            {
                "name": "Beef Sundubu Jjigae",
                "name_ko": "차돌 순두부찌개",
                "price": 9500,
                "info_level": "confirmed",
                "allergens": [
                    ("beef", "confirmed", "public_menu", ""),
                    ("soy", "confirmed", "public_menu", "Tofu base"),
                    ("egg", "likely", "cooking_pattern", "Often finished with a raw egg"),
                ],
            },
        ],
    },
    {
        "name": "Hongik Samgyeopsal Grill",
        "name_ko": "홍익 삼겹살집",
        "address": "서울 마포구 와우산로 21길 8",
        "latitude": 37.5524,
        "longitude": 126.9246,
        "category": "Korean - BBQ",
        "description": "Classic Korean pork belly BBQ restaurant.",
        "source_type": "public_menu",
        "menus": [
            {
                "name": "Grilled Pork Belly",
                "name_ko": "삼겹살",
                "price": 16000,
                "info_level": "confirmed",
                "allergens": [
                    ("pork", "confirmed", "public_menu", ""),
                ],
            },
            {
                "name": "Doenjang Jjigae (side stew)",
                "name_ko": "된장찌개",
                "price": 0,
                "info_level": "pattern",
                "allergens": [
                    ("soy", "confirmed", "cooking_pattern", "Fermented soybean paste base"),
                    ("shellfish", "possible", "cooking_pattern", "Sometimes made with shrimp/anchovy stock"),
                ],
            },
        ],
    },
    {
        "name": "Wau Mountain Naengmyeon",
        "name_ko": "와우산 냉면",
        "address": "서울 마포구 양화로 45",
        "latitude": 37.5536,
        "longitude": 126.9221,
        "category": "Korean - Noodles",
        "description": "Cold buckwheat noodles (naengmyeon) shop.",
        "source_type": "public_menu",
        "menus": [
            {
                "name": "Mul Naengmyeon (cold noodle soup)",
                "name_ko": "물냉면",
                "price": 11000,
                "info_level": "confirmed",
                "allergens": [
                    ("buckwheat", "confirmed", "public_menu", "Noodles are buckwheat-based"),
                    ("egg", "confirmed", "public_menu", "Topped with half a boiled egg"),
                    ("beef", "likely", "cooking_pattern", "Broth is usually beef-based"),
                ],
            },
            {
                "name": "Bibim Naengmyeon (spicy mixed noodle)",
                "name_ko": "비빔냉면",
                "price": 11000,
                "info_level": "confirmed",
                "allergens": [
                    ("buckwheat", "confirmed", "public_menu", "Noodles are buckwheat-based"),
                    ("egg", "confirmed", "public_menu", "Topped with half a boiled egg"),
                ],
            },
        ],
    },
    {
        "name": "Hongdae Fried Chicken & Beer",
        "name_ko": "홍대 치킨호프",
        "address": "서울 마포구 어울마당로 25",
        "latitude": 37.5519,
        "longitude": 126.9218,
        "category": "Korean - Chicken",
        "description": "Korean fried chicken and draft beer pub, popular with international students.",
        "source_type": "public_menu",
        "menus": [
            {
                "name": "Original Fried Chicken",
                "name_ko": "후라이드 치킨",
                "price": 20000,
                "info_level": "confirmed",
                "allergens": [
                    ("chicken", "confirmed", "public_menu", ""),
                    ("wheat", "confirmed", "public_menu", "Wheat-flour batter"),
                    ("egg", "likely", "cooking_pattern", "Batter often contains egg"),
                ],
            },
            {
                "name": "Yangnyeom (spicy sauced) Chicken",
                "name_ko": "양념치킨",
                "price": 21000,
                "info_level": "confirmed",
                "allergens": [
                    ("chicken", "confirmed", "public_menu", ""),
                    ("wheat", "confirmed", "public_menu", "Wheat-flour batter"),
                    ("soy", "likely", "cooking_pattern", "Sauce typically contains soy sauce"),
                    ("peanut", "possible", "cooking_pattern", "Sometimes garnished with crushed peanuts"),
                ],
            },
        ],
    },
    {
        "name": "Mapo Ganjang Gejang House",
        "name_ko": "마포 간장게장",
        "address": "서울 마포구 독막로 9길 15",
        "latitude": 37.5497,
        "longitude": 126.9257,
        "category": "Korean - Seafood",
        "description": "Soy-marinated raw crab (ganjang gejang) specialty restaurant.",
        "source_type": "general_pattern",
        "menus": [
            {
                "name": "Ganjang Gejang Set",
                "name_ko": "간장게장 정식",
                "price": 28000,
                "info_level": "pattern",
                "allergens": [
                    ("shellfish", "confirmed", "cooking_pattern", "Raw crab marinated in soy sauce"),
                    ("soy", "confirmed", "cooking_pattern", "Soy sauce marinade"),
                    ("wheat", "possible", "cooking_pattern", "Soy sauce may contain wheat"),
                ],
            },
        ],
    },
    {
        "name": "Unnamed Toast & Coffee Cart",
        "name_ko": "이름없는 토스트",
        "address": "서울 마포구 홍익로3길 20",
        "latitude": 37.5546,
        "longitude": 126.9252,
        "category": "Cafe - Toast",
        "description": "Street food toast cart; no published ingredient info.",
        "source_type": "no_info",
        "menus": [
            {
                "name": "Ham & Egg Toast",
                "name_ko": "햄에그토스트",
                "price": 3500,
                "info_level": "insufficient",
                "allergens": [],
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the database with sample Hongdae-area restaurants and menu items for local development/demo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing Restaurant/MenuItem/MenuAllergen rows before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            MenuAllergen.objects.all().delete()
            MenuItem.objects.all().delete()
            Restaurant.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing restaurants/menus."))

        created_restaurants = 0
        created_menus = 0
        created_allergens = 0

        for r_data in RESTAURANTS:
            menus = r_data.pop("menus")
            restaurant, r_created = Restaurant.objects.get_or_create(
                name=r_data["name"],
                defaults=r_data,
            )
            created_restaurants += int(r_created)

            for m_data in menus:
                allergens = m_data.pop("allergens")
                menu_item, m_created = MenuItem.objects.get_or_create(
                    restaurant=restaurant,
                    name=m_data["name"],
                    defaults=m_data,
                )
                created_menus += int(m_created)

                for allergen_key, likelihood, source, notes in allergens:
                    _, a_created = MenuAllergen.objects.get_or_create(
                        menu_item=menu_item,
                        allergen_key=allergen_key,
                        defaults={
                            "likelihood": likelihood,
                            "source": source,
                            "notes": notes,
                        },
                    )
                    created_allergens += int(a_created)

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete: {created_restaurants} restaurants, "
            f"{created_menus} menu items, {created_allergens} allergen tags created."
        ))
