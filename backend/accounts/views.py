from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework import status

from .serializers import RegisterSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
