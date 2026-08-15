from django.db import models
from django.contrib.auth.models import User
from restaurants.models import Restaurant
from menus.models import MenuItem


class VisitFeedback(models.Model):
    """
    User's post-visit feedback about a restaurant/menu.
    """
    class YesNoUnsure(models.TextChoices):
        YES = 'yes', 'Yes'
        NO = 'no', 'No'
        UNSURE = 'unsure', 'Unsure'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='feedbacks')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.SET_NULL, null=True, blank=True)

    # Staff response
    staff_provided_info = models.CharField(
        max_length=10, choices=YesNoUnsure.choices, blank=True,
    )
    staff_offered_modification = models.CharField(
        max_length=10, choices=YesNoUnsure.choices, blank=True,
    )
    info_matched_reality = models.CharField(
        max_length=10, choices=YesNoUnsure.choices, blank=True,
    )

    # Allergy reaction
    had_reaction = models.BooleanField(default=False)
    reaction_description = models.TextField(blank=True)

    # Photo
    photo = models.ImageField(upload_to='feedback_photos/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback by {self.user.email} - {self.restaurant.name}"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Visit feedbacks'
