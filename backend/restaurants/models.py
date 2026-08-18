from django.db import models


class Restaurant(models.Model):
    class SuitabilityLevel(models.TextChoices):
        SAFE = 'safe', 'Likely Safe'
        CAUTION = 'caution', 'Caution Needed'
        INSUFFICIENT = 'insufficient', 'Insufficient Info'

    name = models.CharField(max_length=200)
    name_ko = models.CharField(max_length=200, help_text='Korean name')
    address = models.CharField(max_length=500)
    latitude = models.FloatField()
    longitude = models.FloatField()
    category = models.CharField(max_length=100, default='Korean')
    description = models.TextField(blank=True)
    source_type = models.CharField(
        max_length=50,
        blank=True,
        help_text='e.g. public_menu, general_pattern, no_info',
    )
    is_active = models.BooleanField(default=True)

    # Enriched via Kakao Local API (see restaurants/kakao.py + the
    # enrich_restaurants_kakao management command). Kakao doesn't provide
    # business hours, so that's not modeled here - handle it separately
    # (manual entry) if it turns out to be needed.
    phone = models.CharField(max_length=30, blank=True)
    kakao_place_id = models.CharField(max_length=50, blank=True, db_index=True)
    kakao_category = models.CharField(max_length=100, blank=True)
    kakao_place_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.name_ko})"

    class Meta:
        ordering = ['name']
