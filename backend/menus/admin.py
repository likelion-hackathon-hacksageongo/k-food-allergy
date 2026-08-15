from django.contrib import admin
from .models import MenuItem, MenuAllergen


class MenuAllergenInline(admin.TabularInline):
    model = MenuAllergen
    extra = 1


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'restaurant', 'info_level']
    list_filter = ['info_level', 'restaurant']
    search_fields = ['name', 'name_ko']
    inlines = [MenuAllergenInline]
