from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    FuelType, Address, Order, OrderStatusLog,
    DriverLocation, Notification, ServiceArea
)

User = get_user_model()


# ── Auth Serializers ────────────────────────────────────────────
class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, min_length=6)
    password2 = serializers.CharField(write_only=True, label='Confirm Password')

    class Meta:
        model  = User
        fields = ['id', 'phone', 'email', 'first_name', 'last_name',
                  'password', 'password2', 'role']
        extra_kwargs = {'role': {'read_only': True}}

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password2'):
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        phone    = validated_data['phone']
        validated_data.setdefault('username', phone)
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class DriverRegisterSerializer(RegisterSerializer):
    """Admin-only: create driver accounts."""
    class Meta(RegisterSerializer.Meta):
        extra_kwargs = {}   # allow role field


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['id', 'phone', 'email', 'first_name', 'last_name',
                  'profile_pic', 'address', 'role', 'is_verified', 'created_at']
        read_only_fields = ['phone', 'role', 'is_verified', 'created_at']


class UserMiniSerializer(serializers.ModelSerializer):
    """Compact user info used inside other serializers."""
    class Meta:
        model  = User
        fields = ['id', 'phone', 'first_name', 'last_name', 'role']


# ── Fuel Type ───────────────────────────────────────────────────
class FuelTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FuelType
        fields = '__all__'


# ── Address ─────────────────────────────────────────────────────
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Address
        fields = '__all__'
        read_only_fields = ['user']

    def create(self, validated_data):
        user = self.context['request'].user
        # If first address or marked default → clear others
        if validated_data.get('is_default') or \
                not Address.objects.filter(user=user).exists():
            Address.objects.filter(user=user).update(is_default=False)
            validated_data['is_default'] = True
        return Address.objects.create(user=user, **validated_data)


# ── Order ───────────────────────────────────────────────────────
class OrderStatusLogSerializer(serializers.ModelSerializer):
    changed_by = UserMiniSerializer(read_only=True)

    class Meta:
        model  = OrderStatusLog
        fields = '__all__'


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Order
        fields = ['fuel_type', 'quantity_ltr', 'delivery_address',
                  'delivery_address_text', 'payment_method', 'scheduled_time']

    def validate(self, attrs):
        fuel      = attrs['fuel_type']
        qty       = attrs['quantity_ltr']
        if not fuel.is_available:
            raise serializers.ValidationError('This fuel type is currently unavailable.')
        if qty < fuel.min_quantity or qty > fuel.max_quantity:
            raise serializers.ValidationError(
                f'Quantity must be between {fuel.min_quantity}L and {fuel.max_quantity}L.'
            )
        return attrs

    def create(self, validated_data):
        fuel = validated_data['fuel_type']
        validated_data['customer']      = self.context['request'].user
        validated_data['price_per_ltr'] = fuel.price_per_ltr
        validated_data['total_amount']  = (
            validated_data['quantity_ltr'] * fuel.price_per_ltr
        )
        # Snapshot address text if address object given but text not provided
        addr = validated_data.get('delivery_address')
        if addr and not validated_data.get('delivery_address_text'):
            validated_data['delivery_address_text'] = (
                f"{addr.full_address}, {addr.city}, {addr.state} – {addr.pincode}"
            )
        order = Order.objects.create(**validated_data)
        OrderStatusLog.objects.create(
            order=order, status=order.status, changed_by=order.customer,
            note='Order placed by customer.'
        )
        # Notify customer
        Notification.objects.create(
            user=order.customer,
            title='Order Placed!',
            message=f'Your order #{order.order_number} has been received.',
            order=order,
        )
        return order


class OrderListSerializer(serializers.ModelSerializer):
    fuel_type  = FuelTypeSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model  = Order
        fields = ['id', 'order_number', 'fuel_type', 'quantity_ltr',
                  'total_amount', 'status', 'status_display',
                  'payment_method', 'payment_status', 'created_at', 'scheduled_time']


class OrderDetailSerializer(serializers.ModelSerializer):
    customer    = UserMiniSerializer(read_only=True)
    driver      = UserMiniSerializer(read_only=True)
    fuel_type   = FuelTypeSerializer(read_only=True)
    status_logs = OrderStatusLogSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model  = Order
        fields = '__all__'


# ── Admin: Order Update ─────────────────────────────────────────
class OrderAdminUpdateSerializer(serializers.ModelSerializer):
    """Admin-only partial update for status, driver assignment, notes."""
    class Meta:
        model  = Order
        fields = ['status', 'driver', 'payment_status', 'admin_note', 'delivered_at']

    def update(self, instance, validated_data):
        old_status = instance.status
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        # Auto-set delivered_at
        if validated_data.get('status') == Order.STATUS_DELIVERED and not instance.delivered_at:
            from django.utils import timezone
            instance.delivered_at = timezone.now()
        instance.save()
        new_status = instance.status

        # Log status change
        if old_status != new_status:
            OrderStatusLog.objects.create(
                order=instance, status=new_status,
                changed_by=self.context['request'].user,
                note=f'Status updated by admin.'
            )
            # Notify customer
            Notification.objects.create(
                user=instance.customer,
                title='Order Update',
                message=f'Your order #{instance.order_number} is now: {instance.get_status_display()}.',
                order=instance,
            )
        return instance


# ── Driver ──────────────────────────────────────────────────────
class DriverLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DriverLocation
        fields = '__all__'
        read_only_fields = ['driver', 'updated_at']


class DriverStatusUpdateSerializer(serializers.ModelSerializer):
    """Driver updates delivery status of their assigned order."""
    class Meta:
        model  = Order
        fields = ['status']

    def validate_status(self, value):
        allowed = [Order.STATUS_DISPATCHED, Order.STATUS_DELIVERED]
        if value not in allowed:
            raise serializers.ValidationError('Drivers can only set dispatched or delivered.')
        return value

    def update(self, instance, validated_data):
        old_status = instance.status
        instance.status = validated_data['status']
        if instance.status == Order.STATUS_DELIVERED:
            from django.utils import timezone
            instance.delivered_at = timezone.now()
        instance.save()
        if old_status != instance.status:
            OrderStatusLog.objects.create(
                order=instance, status=instance.status,
                changed_by=self.context['request'].user,
                note='Status updated by driver.'
            )
            Notification.objects.create(
                user=instance.customer,
                title='Order Update',
                message=f'Your order #{instance.order_number} is now: {instance.get_status_display()}.',
                order=instance,
            )
        return instance


# ── Notification ────────────────────────────────────────────────
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Notification
        fields = '__all__'
        read_only_fields = ['user', 'created_at']


# ── Service Area ─────────────────────────────────────────────────
class ServiceAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ServiceArea
        fields = '__all__'


# ── Dashboard Stats (admin) ─────────────────────────────────────
class DashboardStatsSerializer(serializers.Serializer):
    total_orders     = serializers.IntegerField()
    pending_orders   = serializers.IntegerField()
    delivered_orders = serializers.IntegerField()
    total_customers  = serializers.IntegerField()
    total_drivers    = serializers.IntegerField()
    today_revenue    = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_revenue    = serializers.DecimalField(max_digits=12, decimal_places=2)