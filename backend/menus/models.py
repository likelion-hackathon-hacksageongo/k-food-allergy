from django.db import models
from restaurants.models import Restaurant


class MenuItem(models.Model):
    class InfoLevel(models.TextChoices):
        CONFIRMED = 'confirmed', 'Confirmed (Public Menu)'
        PATTERN = 'pattern', 'General Cooking Pattern'
        INSUFFICIENT = 'insufficient', 'Insufficient Info'

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_items')
    name = models.CharField(max_length=200)
    name_ko = models.CharField(max_length=200, help_text='Korean name')
    description = models.TextField(blank=True)
    price = models.IntegerField(null=True, blank=True, help_text='Price in KRW')
    info_level = models.CharField(
        max_length=20,
        choices=InfoLevel.choices,
        default=InfoLevel.INSUFFICIENT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.restaurant.name})"

    class Meta:
        ordering = ['restaurant', 'name']


class MenuAllergen(models.Model):
    """
    Allergen associated with a menu item.
    Tracks the likelihood and source of allergen presence.
    """
    class Likelihood(models.TextChoices):
        CONFIRMED = 'confirmed', 'Confirmed'
        LIKELY = 'likely', 'Likely'
        POSSIBLE = 'possible', 'Possible'
        NONE = 'none', 'None'

    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='allergens')
    allergen_key = models.CharField(max_length=30, help_text='Key from AllergenChoice')
    likelihood = models.CharField(max_length=20, choices=Likelihood.choices)
    source = models.CharField(
        max_length=100,
        blank=True,
        help_text='e.g. public_menu, cooking_pattern, user_feedback',
    )
    notes = models.TextField(blank=True, help_text='Additional context about this allergen')

    def __str__(self):
        return f"{self.menu_item.name} - {self.allergen_key} ({self.likelihood})"

    class Meta:
        unique_together = ['menu_item', 'allergen_key']
