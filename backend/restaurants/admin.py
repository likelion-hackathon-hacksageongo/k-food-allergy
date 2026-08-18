from django.contrib import admin
from .models import Restaurant


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['name', 'name_ko', 'category', 'phone', 'source_type', 'is_active']
    list_filter = ['is_active', 'source_type']
    search_fields = ['name', 'name_ko']
