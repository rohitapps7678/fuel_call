from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


# ── Custom User ─────────────────────────────────────────────────
class User(AbstractUser):
    ROLE_CUSTOMER = 'customer'
    ROLE_DRIVER   = 'driver'
    ROLE_ADMIN    = 'admin'
    ROLE_CHOICES  = [
        (ROLE_CUSTOMER, 'Customer'),
        (ROLE_DRIVER,   'Driver'),
        (ROLE_ADMIN,    'Admin'),
    ]

    role         = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_CUSTOMER)
    phone        = models.CharField(max_length=15, unique=True)
    profile_pic  = models.ImageField(upload_to='profiles/', null=True, blank=True)
    address      = models.TextField(blank=True)
    is_verified  = models.BooleanField(default=False)   # phone / email verification
    created_at   = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD  = 'phone'
    REQUIRED_FIELDS = ['username', 'email']

    def __str__(self):
        return f"{self.get_full_name()} ({self.phone}) [{self.role}]"


# ── Fuel Type / Pricing ─────────────────────────────────────────
class FuelType(models.Model):
    name          = models.CharField(max_length=50)        # e.g. "Diesel", "Petrol"
    price_per_ltr = models.DecimalField(max_digits=8, decimal_places=2)
    min_quantity  = models.DecimalField(max_digits=8, decimal_places=2, default=10)  # litres
    max_quantity  = models.DecimalField(max_digits=8, decimal_places=2, default=500)
    is_available  = models.BooleanField(default=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} @ ₹{self.price_per_ltr}/L"


# ── Delivery Address (reusable) ─────────────────────────────────
class Address(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label       = models.CharField(max_length=50, default='Home')  # Home / Office / Site
    full_address= models.TextField()
    city        = models.CharField(max_length=100)
    state       = models.CharField(max_length=100)
    pincode     = models.CharField(max_length=10)
    latitude    = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude   = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default  = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.label} – {self.user.phone}"


# ── Order ───────────────────────────────────────────────────────
class Order(models.Model):
    STATUS_PLACED      = 'placed'
    STATUS_CONFIRMED   = 'confirmed'
    STATUS_ASSIGNED    = 'assigned'
    STATUS_DISPATCHED  = 'dispatched'
    STATUS_DELIVERED   = 'delivered'
    STATUS_CANCELLED   = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PLACED,     'Placed'),
        (STATUS_CONFIRMED,  'Confirmed'),
        (STATUS_ASSIGNED,   'Driver Assigned'),
        (STATUS_DISPATCHED, 'Out for Delivery'),
        (STATUS_DELIVERED,  'Delivered'),
        (STATUS_CANCELLED,  'Cancelled'),
    ]

    PAYMENT_COD    = 'cod'
    PAYMENT_ONLINE = 'online'
    PAYMENT_CHOICES = [
        (PAYMENT_COD,    'Cash on Delivery'),
        (PAYMENT_ONLINE, 'Online'),
    ]

    PAYMENT_STATUS_PENDING = 'pending'
    PAYMENT_STATUS_PAID    = 'paid'
    PAYMENT_STATUS_FAILED  = 'failed'
    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_STATUS_PENDING, 'Pending'),
        (PAYMENT_STATUS_PAID,    'Paid'),
        (PAYMENT_STATUS_FAILED,  'Failed'),
    ]

    # Relationships
    customer       = models.ForeignKey(User, on_delete=models.PROTECT,
                                       related_name='orders', limit_choices_to={'role': 'customer'})
    driver         = models.ForeignKey(User, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='assigned_orders',
                                       limit_choices_to={'role': 'driver'})
    fuel_type      = models.ForeignKey(FuelType, on_delete=models.PROTECT)
    delivery_address = models.ForeignKey(Address, on_delete=models.PROTECT, null=True, blank=True)

    # Order details
    order_number   = models.CharField(max_length=20, unique=True, editable=False)
    quantity_ltr   = models.DecimalField(max_digits=8, decimal_places=2)   # litres
    price_per_ltr  = models.DecimalField(max_digits=8, decimal_places=2)   # snapshot at order time
    total_amount   = models.DecimalField(max_digits=10, decimal_places=2)

    # Address snapshot (in case address gets deleted)
    delivery_address_text = models.TextField()

    # Status & payment
    status         = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PLACED)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default=PAYMENT_COD)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES,
                                      default=PAYMENT_STATUS_PENDING)

    # Timestamps
    scheduled_time = models.DateTimeField(null=True, blank=True)   # customer can schedule delivery
    delivered_at   = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    # Admin notes
    admin_note     = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        if not self.total_amount:
            self.total_amount = self.quantity_ltr * self.price_per_ltr
        super().save(*args, **kwargs)

    def _generate_order_number(self):
        import random, string
        ts = timezone.now().strftime('%Y%m%d%H%M%S')
        rand = ''.join(random.choices(string.digits, k=4))
        return f"FC{ts}{rand}"

    def __str__(self):
        return f"Order {self.order_number} – {self.customer.phone}"


# ── Order Status Log (timeline) ─────────────────────────────────
class OrderStatusLog(models.Model):
    order      = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_logs')
    status     = models.CharField(max_length=15, choices=Order.STATUS_CHOICES)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    note       = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.order.order_number} → {self.status}"


# ── Driver Location (live tracking stub) ────────────────────────
class DriverLocation(models.Model):
    driver    = models.OneToOneField(User, on_delete=models.CASCADE,
                                     related_name='location',
                                     limit_choices_to={'role': 'driver'})
    latitude  = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_online = models.BooleanField(default=False)
    updated_at= models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Driver {self.driver.phone} – {'Online' if self.is_online else 'Offline'}"


# ── Notification ────────────────────────────────────────────────
class Notification(models.Model):
    TYPE_ORDER   = 'order'
    TYPE_PROMO   = 'promo'
    TYPE_SYSTEM  = 'system'
    TYPE_CHOICES = [
        (TYPE_ORDER,  'Order Update'),
        (TYPE_PROMO,  'Promotion'),
        (TYPE_SYSTEM, 'System'),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title      = models.CharField(max_length=200)
    message    = models.TextField()
    notif_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_ORDER)
    is_read    = models.BooleanField(default=False)
    order      = models.ForeignKey(Order, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='notifications')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notif for {self.user.phone}: {self.title}"


# ── Service Area ─────────────────────────────────────────────────
class ServiceArea(models.Model):
    name       = models.CharField(max_length=100)
    pincodes   = models.TextField(help_text="Comma separated pincodes")
    is_active  = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def pincode_list(self):
        return [p.strip() for p in self.pincodes.split(',')]