"""Billing domain exceptions → HTTP 402/403 at the API layer."""


class BillingError(Exception):
    code = "billing_error"
    http_status = 403

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}

    def as_response_data(self) -> dict:
        return {
            "error": self.message,
            "code": self.code,
            "details": self.details,
        }


class FeatureNotAvailable(BillingError):
    code = "feature_not_available"
    http_status = 403


class QuotaExceeded(BillingError):
    code = "quota_exceeded"
    http_status = 402  # Payment Required — usage limit hit
