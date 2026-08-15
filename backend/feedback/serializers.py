from rest_framework import serializers
from .models import VisitFeedback


class VisitFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitFeedback
        fields = [
            'id', 'restaurant', 'menu_item',
            'staff_provided_info', 'staff_offered_modification',
            'info_matched_reality',
            'had_reaction', 'reaction_description',
            'photo', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
