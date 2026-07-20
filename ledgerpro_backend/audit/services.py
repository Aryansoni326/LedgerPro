import logging

from .models import AuditLog, FirmAccessLog

logger = logging.getLogger(__name__)


def _client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_audit(
    *,
    user,
    firm,
    resource_type: str,
    resource_id: int,
    action: str,
    details: dict | None = None,
    request=None,
) -> AuditLog:
    """Persist an immutable audit record and mirror to application logs."""
    entry = AuditLog.objects.create(
        user=user,
        firm=firm,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        details=details or {},
        ip_address=_client_ip(request),
    )
    logger.info(
        "AUDIT user=%s firm=%s action=%s resource=%s:%s ip=%s",
        getattr(user, 'email', None),
        getattr(firm, 'id', None),
        action,
        resource_type,
        resource_id,
        entry.ip_address,
    )
    return entry


def log_firm_access(*, user, firm, request=None) -> FirmAccessLog:
    """Record a firm login / access event for owner activity feeds."""
    user_agent = ''
    if request is not None:
        user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:512]
    entry = FirmAccessLog.objects.create(
        user=user,
        firm=firm,
        event_type=FirmAccessLog.EVENT_LOGIN,
        ip_address=_client_ip(request),
        user_agent=user_agent,
    )
    logger.info(
        "FIRM_ACCESS user=%s firm=%s event=login ip=%s",
        getattr(user, 'email', None),
        getattr(firm, 'id', None),
        entry.ip_address,
    )
    return entry


def log_firm_access_for_user_firms(*, user, firms, request=None) -> int:
    """Log a login access event for each firm in the queryset/iterable."""
    count = 0
    for firm in firms:
        log_firm_access(user=user, firm=firm, request=request)
        count += 1
    return count
