from rest_framework import permissions


class HasFirmAccess(permissions.BasePermission):
    """
    Custom permission to only allow the accountant who created the firm
    to view or edit its details.
    """
    message = 'You do not have access to this firm.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # Enforce that only the accountant who created the firm can access its data
        return obj.created_by == request.user
