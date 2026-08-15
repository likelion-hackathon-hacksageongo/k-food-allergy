from rest_framework import generics, permissions
from .models import VisitFeedback
from .serializers import VisitFeedbackSerializer


class FeedbackCreateView(generics.CreateAPIView):
    """Submit post-visit feedback."""
    serializer_class = VisitFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FeedbackListView(generics.ListAPIView):
    """List user's own feedbacks."""
    serializer_class = VisitFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return VisitFeedback.objects.filter(user=self.request.user)
