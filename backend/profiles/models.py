from django.db import models
from django.contrib.auth.models import User


class AllergenChoice(models.TextChoices):
    SHELLFISH = 'shellfish', 'Shellfish (Shrimp, Crab, Lobster)'
    NUTS = 'nuts', 'Tree Nuts (Walnut, Almond, Pine Nut)'
    WHEAT = 'wheat', 'Wheat / Gluten'
    SOY = 'soy', 'Soy (Tofu, Doenjang, Ganjang)'
    EGG = 'egg', 'Egg'
    DAIRY = 'dairy', 'Dairy (Milk, Cheese, Butter)'
    FISH = 'fish', 'Fish (Anchovy, Mackerel, Tuna)'
    MOLLUSK = 'mollusk', 'Mollusk (Abalone, Squid, Clam)'
    PEACH = 'peach', 'Peach'
    PEANUT = 'peanut', 'Peanut'
    PORK = 'pork', 'Pork'
    BEEF = 'beef', 'Beef'
    CHICKEN = 'chicken', 'Chicken'
    SULFITES = 'sulfites', 'Sulfites (Wine, Vinegar)'
    BUCKWHEAT = 'buckwheat', 'Buckwheat'
    TOMATO = 'tomato', 'Tomato'


class LanguageChoice(models.TextChoices):
    KOREAN = 'ko', 'Korean'
    ENGLISH = 'en', 'English'
    CHINESE = 'zh', 'Chinese'
    JAPANESE = 'ja', 'Japanese'
    VIETNAMESE = 'vi', 'Vietnamese'
    THAI = 'th', 'Thai'
    FRENCH = 'fr', 'French'
    SPANISH = 'es', 'Spanish'
    GERMAN = 'de', 'German'
    RUSSIAN = 'ru', 'Russian'
    INDONESIAN = 'id', 'Indonesian'
    OTHER = 'other', 'Other'


class AllergyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='allergy_profile')
    allergens = models.JSONField(
        default=list,
        help_text='List of allergen keys from AllergenChoice',
    )
    preferred_language = models.CharField(
        max_length=10,
        choices=LanguageChoice.choices,
        default=LanguageChoice.ENGLISH,
        help_text='Used to generate on-site inquiry phrases in the user\'s language (Step 5 of the plan).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {', '.join(self.allergens)}"
