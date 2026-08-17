import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from restaurants.models import Restaurant
from menus.models import MenuItem, MenuAllergen

"""
Batch ingestion of AI's allergen analysis output.

Contract (JSON file, list of menu item entries):

[
  {
    "restaurant": "Hongdae Sundubu House",   # Restaurant.name (exact match)
    "menu_item": "Seafood Sundubu Jjigae",   # MenuItem.name (exact match, under that restaurant)
    "info_level": "confirmed",               # confirmed | pattern | insufficient
    "allergens": [
      {
        "allergen_key": "shellfish",         # must be a key from profiles.models.AllergenChoice
        "likelihood": "confirmed",           # confirmed | likely | possible | none
        "source": "ai_inference",            # free text, e.g. ai_inference / cooking_pattern / public_menu
        "notes": "Contains shrimp and clams"
      }
    ]
  },
  ...
]

Unknown restaurant/menu_item names are skipped and reported at the end
(they need to exist already — this command doesn't create restaurants).
Existing MenuAllergen rows for the same (menu_item, allergen_key) are
updated in place; matching is idempotent, safe to re-run.
"""


class Command(BaseCommand):
    help = "Import AI-generated allergen analysis (batch) into MenuItem/MenuAllergen."

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="Path to the analysis JSON file.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and print a summary without writing to the database.",
        )

    def handle(self, *args, **options):
        path = options["file"]
        try:
            with open(path, encoding="utf-8") as f:
                entries = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {path}")
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}")

        updated_menus = 0
        updated_allergens = 0
        skipped = []

        with transaction.atomic():
            for entry in entries:
                restaurant_name = entry.get("restaurant")
                menu_name = entry.get("menu_item")

                restaurant = Restaurant.objects.filter(name=restaurant_name).first()
                if restaurant is None:
                    skipped.append(f"Unknown restaurant: {restaurant_name!r}")
                    continue

                menu_item = MenuItem.objects.filter(restaurant=restaurant, name=menu_name).first()
                if menu_item is None:
                    skipped.append(f"Unknown menu item: {menu_name!r} @ {restaurant_name!r}")
                    continue

                info_level = entry.get("info_level")
                if info_level and info_level != menu_item.info_level:
                    menu_item.info_level = info_level
                    if not options["dry_run"]:
                        menu_item.save(update_fields=["info_level"])
                    updated_menus += 1

                for a in entry.get("allergens", []):
                    updated_allergens += 1
                    if options["dry_run"]:
                        continue
                    MenuAllergen.objects.update_or_create(
                        menu_item=menu_item,
                        allergen_key=a["allergen_key"],
                        defaults={
                            "likelihood": a["likelihood"],
                            "source": a.get("source", "ai_inference"),
                            "notes": a.get("notes", ""),
                        },
                    )

            if options["dry_run"]:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY RUN] ' if options['dry_run'] else ''}"
            f"{updated_menus} menu items updated, {updated_allergens} allergen tags processed."
        ))
        if skipped:
            self.stdout.write(self.style.WARNING(f"{len(skipped)} entries skipped:"))
            for s in skipped:
                self.stdout.write(f"  - {s}")
