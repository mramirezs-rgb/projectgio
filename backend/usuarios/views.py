from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import GIOTokenObtainPairSerializer

class LoginView(TokenObtainPairView):
    serializer_class = GIOTokenObtainPairSerializer