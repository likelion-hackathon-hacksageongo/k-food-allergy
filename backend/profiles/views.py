from rest_framework import generics, permissions
from .models import AllergyProfile
from .serializers import AllergyProfileSerializer


class AllergyProfileView(generics.RetrieveUpdateAPIView):
    """
    GET: Retrieve current user's allergy profile.
    PUT/PATCH: Create or update allergy profile.
    """
    serializer_class = AllergyProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = AllergyProfile.objects.get_or_create(user=self.request.user)
        return profile
