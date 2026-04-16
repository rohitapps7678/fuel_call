from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, FuelType, Address, Order,
    OrderStatusLog, DriverLocation, Notification, ServiceArea
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ['phone', 'first_name', 'last_name', 'role', 'is_active', 'created_at']
    list_filter   = ['role', 'is_active', 'is_verified']
    search_fields = ['phone', 'first_name', 'last_name', 'email']
    ordering      = ['-created_at']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('FuelCall Info', {'fields': ('role', 'phone', 'profile_pic', 'address', 'is_verified')}),
    )


@admin.register(FuelType)
class FuelTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_per_ltr', 'min_quantity', 'max_quantity', 'is_available', 'updated_at']
    list_editable = ['price_per_ltr', 'is_available']


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display  = ['user', 'label', 'city', 'pincode', 'is_default']
    search_fields = ['user__phone', 'city', 'pincode']


class OrderStatusLogInline(admin.TabularInline):
    model  = OrderStatusLog
    extra  = 0
    readonly_fields = ['status', 'changed_by', 'note', 'created_at']
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display   = ['order_number', 'customer', 'driver', 'fuel_type',
                      'quantity_ltr', 'total_amount', 'status', 'payment_method',
                      'payment_status', 'created_at']
    list_filter    = ['status', 'payment_method', 'payment_status', 'fuel_type']
    search_fields  = ['order_number', 'customer__phone', 'customer__first_name']
    list_editable  = ['status', 'driver']
    readonly_fields = ['order_number', 'price_per_ltr', 'total_amount', 'created_at', 'updated_at']
    inlines        = [OrderStatusLogInline]
    date_hierarchy = 'created_at'


@admin.register(DriverLocation)
class DriverLocationAdmin(admin.ModelAdmin):
    list_display = ['driver', 'latitude', 'longitude', 'is_online', 'updated_at']
    list_filter  = ['is_online']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'notif_type', 'is_read', 'created_at']
    list_filter  = ['notif_type', 'is_read']
    search_fields = ['user__phone', 'title']


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_editable = ['is_active']