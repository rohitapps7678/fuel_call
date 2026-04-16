from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Request user must have role='admin' or be Django superuser."""
    message = 'Admin access required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'admin' or request.user.is_superuser)
        )


class IsDriver(BasePermission):
    """Request user must have role='driver'."""
    message = 'Driver access required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'driver'
        )


class IsCustomer(BasePermission):
    """Request user must have role='customer'."""
    message = 'Customer access required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'customer'
        )


class IsAdminOrDriver(BasePermission):
    """Admin or Driver."""
    message = 'Admin or Driver access required.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role in ['admin', 'driver'] or request.user.is_superuser)
        )