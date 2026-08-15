from django.contrib import admin
from .models import VisitFeedback


@admin.register(VisitFeedback)
class VisitFeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'restaurant', 'had_reaction', 'created_at']
    list_filter = ['had_reaction', 'created_at']
