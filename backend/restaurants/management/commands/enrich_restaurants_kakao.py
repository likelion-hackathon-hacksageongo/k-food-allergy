import time

from django.core.management.base import BaseCommand, CommandError

from restaurants.kakao import search_place, KakaoAPIError
from restaurants.models import Restaurant

"""
Fill in phone / kakao_category / kakao_place_url / kakao_place_id for
restaurants by searching Kakao Local with "<name> <address>" as the query,
biased toward the restaurant's existing lat/lng.

Only fills in fields that are currently blank, unless --overwrite is passed.
Doesn't touch business hours - Kakao's search API doesn't provide that.

Usage:
    python manage.py enrich_restaurants_kakao              # only unenriched restaurants
    python manage.py enrich_restaurants_kakao --all         # re-check every restaurant
    python manage.py enrich_restaurants_kakao --overwrite    # replace existing values too
    python manage.py enrich_restaurants_kakao --dry-run
"""


class Command(BaseCommand):
    help = "Enrich Restaurant rows with phone/category/place link via Kakao Local API."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Re-check every restaurant, not just blank ones.")
        parser.add_argument("--overwrite", action="store_true", help="Overwrite existing phone/category/place_url values.")
        parser.add_argument("--dry-run", action="store_true", help="Don't write to the database, just print results.")

    def handle(self, *args, **options):
        queryset = Restaurant.objects.all() if options["all"] else Restaurant.objects.filter(kakao_place_id="")

        updated = 0
        not_found = []
        errors = []

        for restaurant in queryset:
            query = f"{restaurant.name_ko or restaurant.name} {restaurant.address}"
            try:
                result = search_place(query, longitude=restaurant.longitude, latitude=restaurant.latitude)
            except KakaoAPIError as e:
                errors.append(f"{restaurant.name}: {e}")
                continue

            if result is None:
                not_found.append(restaurant.name)
                continue

            fields_to_update = []
            for model_field, kakao_field in [
                ("phone", "phone"),
                ("kakao_category", "category_name"),
                ("kakao_place_url", "place_url"),
                ("kakao_place_id", "id"),
            ]:
                current = getattr(restaurant, model_field)
                if current and not options["overwrite"]:
                    continue
                setattr(restaurant, model_field, result[kakao_field] if kakao_field in result else result.get(kakao_field, ""))
                fields_to_update.append(model_field)

            if fields_to_update:
                self.stdout.write(f"{restaurant.name} -> {result['place_name']} ({result['phone'] or 'no phone'})")
                if not options["dry_run"]:
                    restaurant.save(update_fields=fields_to_update)
                updated += 1

            time.sleep(0.1)  # be polite to the API

        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY RUN] ' if options['dry_run'] else ''}{updated} restaurants updated."
        ))
        if not_found:
            self.stdout.write(self.style.WARNING(f"{len(not_found)} not found on Kakao: {', '.join(not_found)}"))
        if errors:
            self.stdout.write(self.style.ERROR(f"{len(errors)} errors:"))
            for e in errors:
                self.stdout.write(f"  - {e}")
