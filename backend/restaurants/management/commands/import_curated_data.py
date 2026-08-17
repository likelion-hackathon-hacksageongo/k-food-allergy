import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from restaurants.models import Restaurant
from menus.models import MenuItem, MenuAllergen

"""
Import the Data team's curated CSVs (data/curated/*.csv, see data/SCHEMA.md)
into Restaurant / MenuItem / MenuAllergen.

Files read (all under --data-dir, default <repo root>/data/curated):
  restaurants.csv         -> Restaurant (matched/upserted by name_ko)
  menus.csv               -> MenuItem (matched/upserted by restaurant + name_ko)
  menu_ingredients.csv    -> per-menu ingredient exceptions (add/remove)
  pattern_ingredients.csv -> base ingredients inherited via menus.csv's pattern_key
  ingredient_allergens.csv-> ingredient -> allergen propagation (the actual
                              allergen judgment source - see data/SCHEMA.md #6)

For each menu item: start from its pattern's base ingredients (if
pattern_key is set), apply menu_ingredients.csv add/remove exceptions on
top, then resolve every resulting ingredient to its allergens via
ingredient_allergens.csv and upsert MenuAllergen rows. If an allergen is
reachable through more than one ingredient, the highest-likelihood one
wins (confirmed > likely > possible > none).

Safe to re-run (upserts throughout).
"""

LIKELIHOOD_RANK = {'confirmed': 3, 'likely': 2, 'possible': 1, 'none': 0}


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def _bool(value: str, default: bool = True) -> bool:
    if not value:
        return default
    return value.strip().lower() in ('true', '1', 'yes')


class Command(BaseCommand):
    help = "Import Data team's curated CSVs (data/curated/) into Restaurant/MenuItem/MenuAllergen."

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir',
            type=str,
            default=None,
            help='Path to the curated/ directory (default: <repo root>/data/curated)',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir']) if options['data_dir'] else Path(settings.BASE_DIR).parent / 'data' / 'curated'
        if not data_dir.exists():
            raise CommandError(f"Data dir not found: {data_dir}")

        restaurants_rows = _read_csv(data_dir / 'restaurants.csv')
        if not restaurants_rows:
            raise CommandError(f"No restaurants.csv (or it's empty) in {data_dir}")
        menus_rows = _read_csv(data_dir / 'menus.csv')
        menu_ingredients_rows = _read_csv(data_dir / 'menu_ingredients.csv')
        pattern_ingredients_rows = _read_csv(data_dir / 'pattern_ingredients.csv')
        ingredient_allergens_rows = _read_csv(data_dir / 'ingredient_allergens.csv')

        # Pre-index the lookup tables we'll need repeatedly.
        pattern_base: dict[str, dict[str, dict]] = {}  # pattern_key -> {ingredient_key: {presence, role}}
        for row in pattern_ingredients_rows:
            pattern_base.setdefault(row['pattern_key'], {})[row['ingredient_key']] = {
                'presence': row.get('presence', ''),
                'role': row.get('role', ''),
            }

        menu_exceptions: dict[tuple[str, str], list[dict]] = {}  # (restaurant_key, menu_key) -> [rows]
        for row in menu_ingredients_rows:
            menu_exceptions.setdefault((row['restaurant_key'], row['menu_key']), []).append(row)

        ingredient_allergens: dict[str, list[dict]] = {}  # ingredient_key -> [{allergen_key, likelihood, source_status, notes}]
        for row in ingredient_allergens_rows:
            ingredient_allergens.setdefault(row['ingredient_key'], []).append(row)

        dry_run = options['dry_run']
        stats = {'restaurants': 0, 'menus': 0, 'allergens': 0}
        skipped_menus = []

        with transaction.atomic():
            restaurant_by_key: dict[str, Restaurant] = {}
            for row in restaurants_rows:
                defaults = {
                    'name': row['name'],
                    'name_ko': row['name_ko'],
                    'address': row['address'],
                    'latitude': float(row['latitude']),
                    'longitude': float(row['longitude']),
                    'category': row.get('category') or 'Korean',
                    'description': row.get('description', ''),
                    'source_type': row.get('source_status', ''),
                    'is_active': _bool(row.get('is_active', '')),
                }
                restaurant, created = Restaurant.objects.update_or_create(
                    name_ko=row['name_ko'], defaults=defaults,
                )
                restaurant_by_key[row['key']] = restaurant
                stats['restaurants'] += 1

            for row in menus_rows:
                restaurant = restaurant_by_key.get(row['restaurant_key'])
                if restaurant is None:
                    skipped_menus.append(f"{row['name_ko']}: unknown restaurant_key {row['restaurant_key']!r}")
                    continue

                price = int(row['price_krw']) if row.get('price_krw') else None
                defaults = {
                    'name': row['name'],
                    'name_ko': row['name_ko'],
                    'description': row.get('description', ''),
                    'price': price,
                    'info_level': row.get('info_level') or MenuItem.InfoLevel.INSUFFICIENT,
                }
                menu_item, created = MenuItem.objects.update_or_create(
                    restaurant=restaurant, name_ko=row['name_ko'], defaults=defaults,
                )
                stats['menus'] += 1

                # Resolve this menu's final ingredient set: pattern base + exceptions.
                ingredients = dict(pattern_base.get(row.get('pattern_key', ''), {}))
                for exc in menu_exceptions.get((row['restaurant_key'], row['key']), []):
                    if exc.get('action') == 'remove':
                        ingredients.pop(exc['ingredient_key'], None)
                    else:
                        ingredients[exc['ingredient_key']] = {
                            'presence': exc.get('presence', ''),
                            'role': exc.get('role', ''),
                        }

                # Resolve ingredients -> allergens, keeping the highest
                # likelihood per allergen_key when more than one ingredient
                # implies the same allergen.
                best: dict[str, dict] = {}  # allergen_key -> {likelihood, source, notes}
                for ingredient_key, meta in ingredients.items():
                    for a in ingredient_allergens.get(ingredient_key, []):
                        key = a['allergen_key']
                        candidate = {
                            'likelihood': a['likelihood'],
                            'source': a.get('source_status', 'cooking_pattern'),
                            'notes': (
                                f"{ingredient_key} ({meta.get('presence', '')})"
                                + (f" - {a['notes']}" if a.get('notes') else '')
                            ),
                        }
                        current = best.get(key)
                        if current is None or LIKELIHOOD_RANK.get(candidate['likelihood'], 0) > LIKELIHOOD_RANK.get(current['likelihood'], 0):
                            best[key] = candidate

                for allergen_key, data in best.items():
                    stats['allergens'] += 1
                    if dry_run:
                        continue
                    MenuAllergen.objects.update_or_create(
                        menu_item=menu_item,
                        allergen_key=allergen_key,
                        defaults=data,
                    )

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY RUN] ' if dry_run else ''}"
            f"{stats['restaurants']} restaurants, {stats['menus']} menu items, "
            f"{stats['allergens']} allergen tags processed."
        ))
        if skipped_menus:
            self.stdout.write(self.style.WARNING(f"{len(skipped_menus)} menu rows skipped:"))
            for s in skipped_menus:
                self.stdout.write(f"  - {s}")
