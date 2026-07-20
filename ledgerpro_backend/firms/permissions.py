from rest_framework import permissions


def is_firm_creator(user, firm) -> bool:
    return bool(user and firm and firm.created_by_id == getattr(user, 'id', None))


def is_firm_owner_email(user, firm) -> bool:
    if not user or not firm or not getattr(user, 'email', None) or not firm.owner_email:
        return False
    return firm.owner_email.lower() == user.email.lower()


class HasFirmAccess(permissions.BasePermission):
    """
    Allow the accountant who created the firm full access.
    Allow the firm owner (matched by owner_email) read-only access.
    """
    message = 'You do not have access to this firm.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if is_firm_creator(request.user, obj):
            return True
        if is_firm_owner_email(request.user, obj):
            return request.method in permissions.SAFE_METHODS
        return False


class CanWriteFirm(permissions.BasePermission):
    """Only the creating accountant may mutate firm data."""
    message = 'Owner accounts have read-only access. Changes must be made by your accountant.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return is_firm_creator(request.user, obj)
