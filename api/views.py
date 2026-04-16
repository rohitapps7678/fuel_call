from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import generics, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    FuelType, Address, Order, OrderStatusLog,
    DriverLocation, Notification, ServiceArea
)
from .serializers import (
    RegisterSerializer, DriverRegisterSerializer, UserProfileSerializer,
    UserMiniSerializer, FuelTypeSerializer,
    AddressSerializer, OrderCreateSerializer, OrderListSerializer,
    OrderDetailSerializer, OrderAdminUpdateSerializer,
    DriverLocationSerializer, DriverStatusUpdateSerializer,
    NotificationSerializer, ServiceAreaSerializer, DashboardStatsSerializer
)
from .utils import IsAdmin, IsDriver, IsCustomer, IsAdminOrDriver

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════

class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — Customer self-registration."""
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user   = serializer.save()
        tokens = RefreshToken.for_user(user)
        return Response({
            'user':    UserProfileSerializer(user).data,
            'tokens': {
                'access':  str(tokens.access_token),
                'refresh': str(tokens),
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login/ — Login with phone + password."""
    permission_classes = [AllowAny]

    def post(self, request):
        phone    = request.data.get('phone')
        password = request.data.get('password')

        if not phone or not password:
            return Response({'detail': 'Phone and password are required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response({'detail': 'Invalid credentials.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({'detail': 'Invalid credentials.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'detail': 'Account is disabled.'},
                            status=status.HTTP_403_FORBIDDEN)

        tokens = RefreshToken.for_user(user)
        return Response({
            'user':   UserProfileSerializer(user).data,
            'tokens': {
                'access':  str(tokens.access_token),
                'refresh': str(tokens),
            }
        })


class LogoutView(APIView):
    """POST /api/auth/logout/ — Blacklist refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            RefreshToken(request.data.get('refresh')).blacklist()
        except Exception:
            pass
        return Response({'detail': 'Logged out successfully.'})


class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/profile/"""
    serializer_class   = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user     = request.user
        old_pass = request.data.get('old_password')
        new_pass = request.data.get('new_password')
        if not user.check_password(old_pass):
            return Response({'detail': 'Old password is incorrect.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not new_pass or len(new_pass) < 6:
            return Response({'detail': 'New password must be at least 6 characters.'},
                            status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new_pass)
        user.save()
        return Response({'detail': 'Password changed successfully.'})


# ═══════════════════════════════════════════════════════════════
# FUEL TYPES (public read / admin write)
# ═══════════════════════════════════════════════════════════════

class FuelTypeViewSet(viewsets.ModelViewSet):
    queryset           = FuelType.objects.all()
    serializer_class   = FuelTypeSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAdmin()]


# ═══════════════════════════════════════════════════════════════
# ADDRESSES
# ═══════════════════════════════════════════════════════════════

class AddressViewSet(viewsets.ModelViewSet):
    serializer_class   = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        addr = self.get_object()
        Address.objects.filter(user=request.user).update(is_default=False)
        addr.is_default = True
        addr.save()
        return Response({'detail': 'Default address updated.'})


# ═══════════════════════════════════════════════════════════════
# ORDERS — Customer
# ═══════════════════════════════════════════════════════════════

class OrderCreateView(generics.CreateAPIView):
    """POST /api/orders/ — Customer places an order."""
    serializer_class   = OrderCreateSerializer
    permission_classes = [IsAuthenticated, IsCustomer]


class CustomerOrderListView(generics.ListAPIView):
    """GET /api/orders/ — Customer sees their own orders."""
    serializer_class   = OrderListSerializer
    permission_classes = [IsAuthenticated, IsCustomer]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['status', 'payment_status']
    ordering_fields    = ['created_at']

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)


class CustomerOrderDetailView(generics.RetrieveAPIView):
    """GET /api/orders/<id>/ — Customer sees one order detail."""
    serializer_class   = OrderDetailSerializer
    permission_classes = [IsAuthenticated, IsCustomer]

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)


class CancelOrderView(APIView):
    """POST /api/orders/<id>/cancel/ — Customer cancels a placed order."""
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk, customer=request.user)
        except Order.DoesNotExist:
            return Response({'detail': 'Order not found.'}, status=404)
        if order.status not in [Order.STATUS_PLACED, Order.STATUS_CONFIRMED]:
            return Response({'detail': 'Order cannot be cancelled at this stage.'},
                            status=status.HTTP_400_BAD_REQUEST)
        order.status = Order.STATUS_CANCELLED
        order.save()
        OrderStatusLog.objects.create(
            order=order, status=Order.STATUS_CANCELLED,
            changed_by=request.user, note='Cancelled by customer.'
        )
        return Response({'detail': 'Order cancelled.'})


# ═══════════════════════════════════════════════════════════════
# ORDERS — Admin
# ═══════════════════════════════════════════════════════════════

class AdminOrderListView(generics.ListAPIView):
    """GET /api/admin/orders/ — All orders with filters."""
    serializer_class   = OrderDetailSerializer
    permission_classes = [IsAdmin]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['status', 'payment_status', 'payment_method', 'driver']
    search_fields      = ['order_number', 'customer__phone', 'customer__first_name']
    ordering_fields    = ['created_at', 'total_amount']
    queryset           = Order.objects.select_related('customer', 'driver', 'fuel_type').all()


class AdminOrderDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/admin/orders/<id>/ — Admin views & updates an order."""
    permission_classes = [IsAdmin]
    queryset           = Order.objects.all()

    def get_serializer_class(self):
        if self.request.method in ['PATCH', 'PUT']:
            return OrderAdminUpdateSerializer
        return OrderDetailSerializer


class AdminCustomerListView(generics.ListAPIView):
    """GET /api/admin/customers/ — All customers."""
    serializer_class   = UserProfileSerializer
    permission_classes = [IsAdmin]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['phone', 'first_name', 'last_name', 'email']
    queryset           = User.objects.filter(role='customer')


class AdminDriverCreateView(generics.CreateAPIView):
    """POST /api/admin/drivers/ — Admin creates driver account."""
    serializer_class   = DriverRegisterSerializer
    permission_classes = [IsAdmin]

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['role'] = 'driver'
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(role='driver')
        return Response(UserProfileSerializer(user).data, status=201)


class AdminDriverListView(generics.ListAPIView):
    """GET /api/admin/drivers/ — All drivers."""
    serializer_class   = UserProfileSerializer
    permission_classes = [IsAdmin]
    queryset           = User.objects.filter(role='driver')


class AdminAssignDriverView(APIView):
    """POST /api/admin/orders/<id>/assign-driver/ — Assign driver to order."""
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        driver_id = request.data.get('driver_id')
        try:
            order  = Order.objects.get(pk=pk)
            driver = User.objects.get(pk=driver_id, role='driver')
        except (Order.DoesNotExist, User.DoesNotExist):
            return Response({'detail': 'Order or driver not found.'}, status=404)

        order.driver = driver
        order.status = Order.STATUS_ASSIGNED
        order.save()
        OrderStatusLog.objects.create(
            order=order, status=Order.STATUS_ASSIGNED,
            changed_by=request.user,
            note=f'Driver {driver.get_full_name()} ({driver.phone}) assigned.'
        )
        # Notify customer
        Notification.objects.create(
            user=order.customer,
            title='Driver Assigned',
            message=f'Driver {driver.get_full_name()} has been assigned to your order #{order.order_number}.',
            order=order,
        )
        return Response({'detail': 'Driver assigned.', 'order': OrderDetailSerializer(order).data})


class AdminDashboardView(APIView):
    """GET /api/admin/dashboard/ — Stats overview."""
    permission_classes = [IsAdmin]

    def get(self, request):
        today = timezone.now().date()
        stats = {
            'total_orders':     Order.objects.count(),
            'pending_orders':   Order.objects.exclude(
                                    status__in=[Order.STATUS_DELIVERED, Order.STATUS_CANCELLED]
                                ).count(),
            'delivered_orders': Order.objects.filter(status=Order.STATUS_DELIVERED).count(),
            'total_customers':  User.objects.filter(role='customer').count(),
            'total_drivers':    User.objects.filter(role='driver').count(),
            'today_revenue':    Order.objects.filter(
                                    status=Order.STATUS_DELIVERED,
                                    delivered_at__date=today
                                ).aggregate(r=Sum('total_amount'))['r'] or 0,
            'total_revenue':    Order.objects.filter(
                                    status=Order.STATUS_DELIVERED
                                ).aggregate(r=Sum('total_amount'))['r'] or 0,
        }
        return Response(DashboardStatsSerializer(stats).data)


# ═══════════════════════════════════════════════════════════════
# DRIVER VIEWS
# ═══════════════════════════════════════════════════════════════

class DriverOrderListView(generics.ListAPIView):
    """GET /api/driver/orders/ — Driver sees their assigned orders."""
    serializer_class   = OrderListSerializer
    permission_classes = [IsAuthenticated, IsDriver]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['status']

    def get_queryset(self):
        return Order.objects.filter(driver=self.request.user)


class DriverOrderDetailView(generics.RetrieveAPIView):
    """GET /api/driver/orders/<id>/"""
    serializer_class   = OrderDetailSerializer
    permission_classes = [IsAuthenticated, IsDriver]

    def get_queryset(self):
        return Order.objects.filter(driver=self.request.user)


class DriverUpdateStatusView(generics.UpdateAPIView):
    """PATCH /api/driver/orders/<id>/status/ — Driver updates delivery status."""
    serializer_class   = DriverStatusUpdateSerializer
    permission_classes = [IsAuthenticated, IsDriver]
    http_method_names  = ['patch']

    def get_queryset(self):
        return Order.objects.filter(driver=self.request.user)


class DriverLocationUpdateView(APIView):
    """POST /api/driver/location/ — Driver updates their live location."""
    permission_classes = [IsAuthenticated, IsDriver]

    def post(self, request):
        loc, _ = DriverLocation.objects.get_or_create(driver=request.user)
        serializer = DriverLocationSerializer(
            loc, data=request.data, partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(driver=request.user)
        return Response(serializer.data)


class DriverToggleOnlineView(APIView):
    """POST /api/driver/toggle-online/ — Driver goes online/offline."""
    permission_classes = [IsAuthenticated, IsDriver]

    def post(self, request):
        loc, _ = DriverLocation.objects.get_or_create(
            driver=request.user,
            defaults={'latitude': 0, 'longitude': 0}
        )
        loc.is_online = not loc.is_online
        loc.save()
        return Response({'is_online': loc.is_online})


# ═══════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════

class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/ — User's notifications."""
    serializer_class   = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class MarkNotificationReadView(APIView):
    """POST /api/notifications/<id>/read/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        notif.is_read = True
        notif.save()
        return Response({'detail': 'Marked as read.'})


class MarkAllNotificationsReadView(APIView):
    """POST /api/notifications/read-all/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'detail': 'All notifications marked as read.'})


# ═══════════════════════════════════════════════════════════════
# SERVICE AREA (public)
# ═══════════════════════════════════════════════════════════════

class ServiceAreaListView(generics.ListAPIView):
    """GET /api/service-areas/ — Check if pincode is serviceable."""
    serializer_class   = ServiceAreaSerializer
    permission_classes = [AllowAny]
    queryset           = ServiceArea.objects.filter(is_active=True)


class CheckPincodeView(APIView):
    """GET /api/check-pincode/?pincode=110001"""
    permission_classes = [AllowAny]

    def get(self, request):
        pincode = request.query_params.get('pincode', '').strip()
        if not pincode:
            return Response({'detail': 'pincode query param required.'}, status=400)
        areas = ServiceArea.objects.filter(is_active=True)
        for area in areas:
            if pincode in area.pincode_list():
                return Response({'serviceable': True, 'area': area.name})
        return Response({'serviceable': False})