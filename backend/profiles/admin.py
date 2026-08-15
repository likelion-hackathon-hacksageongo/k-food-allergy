from django.contrib import admin
from .models import AllergyProfile


@admin.register(AllergyProfile)
class AllergyProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'allergens', 'updated_at']
