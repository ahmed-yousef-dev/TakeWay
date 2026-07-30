from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from orders.models import DeliveryAddress
from orders.serializers import DeliveryAddressSerializer

class DeliveryAddressViewSet(viewsets.ModelViewSet):
    """
    CRUD for customer delivery addresses.
    Customers can only manage their own addresses.
    """
    serializer_class = DeliveryAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Only return the logged-in user's active addresses
        return DeliveryAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically assign the logged-in user as the owner
        serializer.save(user=self.request.user)
