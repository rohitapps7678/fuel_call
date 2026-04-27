from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register(r'fuel-types', views.FuelTypeViewSet, basename='fuel-type')
router.register(r'addresses',       views.AddressViewSet,           basename='address')
router.register(r'admin/service-areas', views.AdminServiceAreaViewSet, basename='admin-service-area')

urlpatterns = [

    # ── Router (FuelType + Address) ───────────────────────────
    path('', include(router.urls)),

    # ── Auth ──────────────────────────────────────────────────
    path('auth/register/',        views.RegisterView.as_view(),        name='register'),
    path('auth/login/',           views.LoginView.as_view(),           name='login'),
    path('auth/logout/',          views.LogoutView.as_view(),          name='logout'),
    path('auth/token/refresh/',   TokenRefreshView.as_view(),          name='token-refresh'),
    path('auth/profile/',         views.ProfileView.as_view(),         name='profile'),
    path('auth/change-password/', views.ChangePasswordView.as_view(),  name='change-password'),

    # ── Customer: Orders ──────────────────────────────────────
    path('orders/',               views.OrderCreateView.as_view(),         name='order-create'),
    path('orders/list/',          views.CustomerOrderListView.as_view(),   name='order-list'),
    path('orders/<int:pk>/',      views.CustomerOrderDetailView.as_view(), name='order-detail'),
    path('orders/<int:pk>/cancel/', views.CancelOrderView.as_view(),       name='order-cancel'),

    # ── Notifications ─────────────────────────────────────────
    path('notifications/',              views.NotificationListView.as_view(),       name='notif-list'),
    path('notifications/read-all/',     views.MarkAllNotificationsReadView.as_view(), name='notif-read-all'),
    path('notifications/<int:pk>/read/', views.MarkNotificationReadView.as_view(),  name='notif-read'),

    # ── Service Areas ─────────────────────────────────────────
    path('service-areas/',    views.ServiceAreaListView.as_view(), name='service-areas'),
    path('check-district/',   views.CheckDistrictView.as_view(),   name='check-district'),

    # ── Admin ─────────────────────────────────────────────────
    path('admin/dashboard/',              views.AdminDashboardView.as_view(),    name='admin-dashboard'),
    path('admin/orders/',                 views.AdminOrderListView.as_view(),    name='admin-orders'),
    path('admin/orders/<int:pk>/',        views.AdminOrderDetailView.as_view(),  name='admin-order-detail'),
    path('admin/orders/<int:pk>/assign-driver/', views.AdminAssignDriverView.as_view(), name='admin-assign-driver'),
    path('admin/customers/',              views.AdminCustomerListView.as_view(), name='admin-customers'),
    path('admin/drivers/',                views.AdminDriverListView.as_view(),   name='admin-drivers'),
    path('admin/drivers/create/',         views.AdminDriverCreateView.as_view(), name='admin-driver-create'),

    # ── Driver ───────────────────────────────────────────────
    path('driver/orders/',                views.DriverOrderListView.as_view(),    name='driver-orders'),
    path('driver/orders/<int:pk>/',       views.DriverOrderDetailView.as_view(),  name='driver-order-detail'),
    path('driver/orders/<int:pk>/status/', views.DriverUpdateStatusView.as_view(), name='driver-update-status'),
    path('driver/location/',              views.DriverLocationUpdateView.as_view(), name='driver-location'),
    path('driver/toggle-online/',         views.DriverToggleOnlineView.as_view(),   name='driver-toggle-online'),
]