import hashlib
import hmac
import json
import logging
import secrets
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from .models import OTPVerification, User

logger = logging.getLogger(__name__)


class OTPDeliveryError(RuntimeError):
    """Raised when the verification code could not be delivered to the user."""


OTP_DELIVERY_MESSAGE = (
    'We could not send your verification code by email. '
    'Please try again in a moment or contact support if this continues.'
)


class GoogleAuthService:
    @staticmethod
    def verify_token(token: str) -> dict:
        """
        Verify the Google OAuth ID Token.
        Supports a developer login fallback for testing.
        """
        if token.startswith("mock_dev_token_"):
            if not getattr(settings, 'DEBUG', False):
                raise ValueError("Developer mock login is disabled in production.")
            email = token.replace("mock_dev_token_", "")
            logger.info("Developer simulated Google Login for email: %s", email)
            return {
                "email": email,
                "sub": f"mock_google_sub_{email}",
                "name": email.split("@")[0].capitalize(),
                "picture": "https://www.gravatar.com/avatar/00000000000000000000000000000000?d=mp&f=y"
            }

        try:
            # Verify the token using Google OAuth tokeninfo endpoint
            url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode('utf-8'))

                # Check for errors in Google API response
                if "error_description" in data:
                    raise ValueError(data["error_description"])

                # Verify audience
                aud = data.get("aud")
                client_id = getattr(settings, "GOOGLE_OAUTH_CLIENT_ID", None)
                if client_id and "mock" not in client_id and aud != client_id:
                    raise ValueError("Google ID Token audience mismatch")

                return {
                    "email": data.get("email"),
                    "sub": data.get("sub"),
                    "name": data.get("name", ""),
                    "picture": data.get("picture", "")
                }
        except Exception as e:
            logger.error("Failed to verify Google ID token: %s", e)
            raise ValueError(f"Invalid Google ID token: {str(e)}")

    @staticmethod
    def exchange_code(code: str) -> dict:
        """
        Exchange a Google OAuth authorization code for an ID token,
        then extract and return the user profile.
        """
        client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', None)
        client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', None)
        redirect_uri = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URI', None)

        if not client_id or not client_secret or not redirect_uri:
            raise ValueError("Google OAuth credentials are not configured on the server.")

        try:
            token_url = "https://oauth2.googleapis.com/token"
            payload = {
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            }
            req = urllib.request.Request(
                token_url,
                data=urllib.parse.urlencode(payload).encode('utf-8'),
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                method='POST'
            )
            with urllib.request.urlopen(req) as response:
                token_data = json.loads(response.read().decode('utf-8'))

            id_token = token_data.get('id_token')
            if not id_token:
                raise ValueError("No id_token in Google token response.")

            # Verify the returned ID token
            return GoogleAuthService.verify_token(id_token)

        except Exception as e:
            logger.error("Failed to exchange Google auth code: %s", e)
            raise ValueError(f"Failed to complete Google sign-in: {str(e)}")


class OTPService:
    @staticmethod
    def generate_otp() -> str:
        """Generate a cryptographically secure 6-digit code."""
        return "".join(secrets.choice("0123456789") for _ in range(6))

    @staticmethod
    def hash_otp(code: str, salt: str = '') -> str:
        """HMAC-SHA256 of the OTP code with server secret + per-session salt."""
        key = f"{settings.SECRET_KEY}:{salt}".encode('utf-8')
        return hmac.new(key, code.encode('utf-8'), hashlib.sha256).hexdigest()

    @staticmethod
    def verify_otp_hash(code: str, otp_hash: str, salt: str = '') -> bool:
        expected = OTPService.hash_otp(code, salt)
        return hmac.compare_digest(expected, otp_hash)

    @classmethod
    def create_verification(cls, user: User = None, email: str = None, purpose: str = 'login') -> tuple[OTPVerification, str]:
        """Create a fresh verification record, invalidating previous ones."""
        code = cls.generate_otp()

        # Invalidate any other active verifications matching criteria
        if user:
            OTPVerification.objects.filter(user=user, purpose=purpose, is_verified=False, is_locked=False).update(is_locked=True)
            verification = OTPVerification.objects.create(
                user=user,
                purpose=purpose,
                otp_hash='pending'
            )
        else:
            OTPVerification.objects.filter(email=email, purpose=purpose, is_verified=False, is_locked=False).update(is_locked=True)
            verification = OTPVerification.objects.create(
                email=email,
                purpose=purpose,
                otp_hash='pending'
            )
        # Salt hash with unique pending_token so codes cannot be precomputed
        verification.otp_hash = cls.hash_otp(code, salt=verification.pending_token)
        verification.save(update_fields=['otp_hash'])
        return verification, code

    @staticmethod
    def _build_otp_email(code: str) -> tuple[str, str, str]:
        subject = "LedgerPro — Your Sign-In Verification Code"
        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#fafafa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#fafafa;padding:40px 0;">
    <tr><td align="center">
      <table width="460" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e4e4e7;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
        <!-- Header -->
        <tr>
          <td style="background:#09090b;padding:32px 40px;text-align:center;">
            <div style="display:inline-flex;align-items:center;vertical-align:middle;">
              <!-- Pure SVG of the new premium B&W offset sheets logo -->
              <svg width="32" height="32" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" style="display:inline-block;vertical-align:middle;margin-right:12px;">
                <rect x="4" y="4" width="20" height="26" rx="3.5" fill="#3f3f46" />
                <rect x="9" y="9" width="20" height="26" rx="3.5" fill="#71717a" />
                <rect x="14" y="14" width="20" height="26" rx="3.5" fill="#ffffff" stroke="#09090b" stroke-width="1.5" />
                <line x1="18" y1="20" x2="29" y2="20" stroke="#09090b" stroke-width="2" stroke-linecap="round" />
                <line x1="18" y1="25" x2="29" y2="25" stroke="#09090b" stroke-width="2" stroke-linecap="round" />
                <line x1="18" y1="30" x2="25" y2="30" stroke="#09090b" stroke-width="2" stroke-linecap="round" />
              </svg>
              <span style="font-size:20px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;font-family:inherit;vertical-align:middle;line-height:32px;">Ledger<span style="font-weight:300;color:#a1a1aa;">Pro</span></span>
            </div>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:44px 40px;text-align:center;">
            <h2 style="margin:0 0 12px;font-size:22px;font-weight:700;color:#09090b;letter-spacing:-0.3px;">Verify your sign-in</h2>
            <p style="margin:0 0 32px;font-size:15px;color:#71717a;line-height:1.6;">
              Enter the 6-digit verification code below to complete your sign-in to LedgerPro.<br>
              This code is valid for <strong>5 minutes</strong>.
            </p>
            <!-- OTP Code Box -->
            <div style="display:inline-block;background:#f4f4f5;border:1px solid #e4e4e7;border-radius:8px;padding:18px 36px;margin-bottom:32px;">
              <span style="font-size:38px;font-weight:700;letter-spacing:8px;color:#09090b;font-family:Courier New,Courier,monospace;">{code}</span>
            </div>
            <p style="margin:0;font-size:13px;color:#a1a1aa;line-height:1.5;">
              If you didn't request this code, you can safely ignore this email.<br>
              To protect your account, never share this code with anyone.
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#fafafa;border-top:1px solid #f4f4f5;padding:24px 40px;text-align:center;">
            <p style="margin:0;font-size:12px;color:#a1a1aa;line-height:1.5;">
              © 2026 LedgerPro. All rights reserved.<br>
              This is an automated security transmission. Please do not reply.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
        plain_text = (
            f"LedgerPro — Verify your sign-in\n\n"
            f"Your 6-digit verification code is: {code}\n\n"
            f"This code expires in 5 minutes.\n"
            f"If you did not request this, please ignore this email."
        )
        return subject, html_content, plain_text

    @staticmethod
    def _parse_from_email(value: str) -> tuple[str, str]:
        value = (value or '').strip().strip('"').strip("'")
        if '<' in value and '>' in value:
            name, email = value.rsplit('<', 1)
            return name.strip().strip('"').strip("'"), email.replace('>', '').strip()
        return 'LedgerPro', value.strip()

    @classmethod
    def _validate_resend_from(cls, from_address: str) -> None:
        """Fail fast with actionable errors before calling Resend."""
        address = (from_address or '').strip().lower()
        if not address or '@' not in address:
            raise OTPDeliveryError(
                "DEFAULT_FROM_EMAIL is missing or invalid on the server. "
                "Set it to e.g. LedgerPro <noreply@ledgerpro.store>."
            )

        domain = address.rsplit('@', 1)[-1]
        blocked = (
            'gmail.com', 'googlemail.com', 'yahoo.com', 'outlook.com',
            'hotmail.com', 'live.com', 'icloud.com', 'me.com',
        )
        if domain in blocked:
            raise OTPDeliveryError(
                f"DEFAULT_FROM_EMAIL uses @{domain}, which Resend cannot send from. "
                "Use an address on your verified domain "
                "(e.g. noreply@yourdomain.com), then redeploy."
            )

        if domain.endswith('resend.dev'):
            raise OTPDeliveryError(
                "DEFAULT_FROM_EMAIL still uses @resend.dev, which can only email "
                "your own Resend account address. Verify your domain in Resend, "
                "then set DEFAULT_FROM_EMAIL to noreply@your-domain.com and redeploy."
            )

        placeholders = ('your-verified-domain.com', 'yourdomain.com', 'example.com', 'your-email@')
        if any(p in address for p in placeholders) or 'your-' in address:
            raise OTPDeliveryError(
                "DEFAULT_FROM_EMAIL still looks like a placeholder. "
                "Set a real from-address on your verified Resend domain."
            )

    @classmethod
    def _send_via_resend(cls, email: str, subject: str, html_content: str, plain_text: str) -> bool:
        api_key = getattr(settings, 'RESEND_API_KEY', '').strip()
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'LedgerPro <noreply@ledgerpro.in>')
        if not api_key:
            return False

        from_name, from_address = cls._parse_from_email(from_email)
        cls._validate_resend_from(from_address)
        payload = {
            'from': f'{from_name} <{from_address}>',
            'to': [email],
            'subject': subject,
            'html': html_content,
            'text': plain_text,
        }

        req = urllib.request.Request(
            'https://api.resend.com/emails',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                # Resend sits behind Cloudflare — requests with no User-Agent
                # are rejected with HTTP 403 / error code 1010 before the API runs.
                'User-Agent': 'LedgerPro/1.0 (+https://ledgerpro.store)',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                response_body = response.read().decode('utf-8')
                response_data = json.loads(response_body) if response_body else {}
                logger.info("OTP email sent to %s via Resend (id=%s).", email, response_data.get('id'))
                return True
        except urllib.error.HTTPError as e:
            # Resend explains rejections (unverified domain, bad key, invalid from)
            # in the response body — without reading it the log is just "HTTP 403".
            detail = cls._read_resend_error(e)
            logger.error(
                "Resend rejected OTP email for %s (status=%s, from=%s): %s",
                email, e.code, from_address, detail,
            )
            raise OTPDeliveryError(detail) from e
        except Exception as e:
            logger.error("Resend request failed for %s: %s", email, e, exc_info=True)
            raise OTPDeliveryError(f"Could not reach the email provider: {e}") from e

    @staticmethod
    def _read_resend_error(error: 'urllib.error.HTTPError') -> str:
        try:
            body = error.read().decode('utf-8')
        except Exception:
            return f"HTTP {error.code} from Resend with no readable body."

        try:
            data = json.loads(body)
        except ValueError:
            return f"HTTP {error.code} from Resend: {body[:300]}"

        message = data.get('message') or data.get('error') or body[:300]
        name = data.get('name')
        return f"{message} (resend_error={name}, status={error.code})" if name else f"{message} (status={error.code})"

    @classmethod
    def _console_fallback_allowed(cls) -> bool:
        return bool(
            getattr(settings, 'DEBUG', False)
            and getattr(settings, 'OTP_CONSOLE_FALLBACK', False)
        )

    @classmethod
    def send_otp_email(cls, email: str, code: str):
        """
        Send the OTP code via Resend, then SMTP, then optional console fallback.
        """
        subject, html_content, plain_text = cls._build_otp_email(code)
        api_key = (getattr(settings, 'RESEND_API_KEY', '') or '').strip()

        if api_key:
            cls._send_via_resend(email, subject, html_content, plain_text)
            return

        smtp_host = getattr(settings, 'EMAIL_HOST', None)
        smtp_user = getattr(settings, 'EMAIL_HOST_USER', None)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'LedgerPro <noreply@ledgerpro.in>')

        if smtp_host and smtp_user:
            try:
                from django.core.mail import EmailMultiAlternatives
                msg = EmailMultiAlternatives(subject, plain_text, from_email, [email])
                msg.attach_alternative(html_content, "text/html")
                msg.send()
                logger.info("OTP email sent to %s via SMTP.", email)
                return
            except Exception as e:
                logger.error("SMTP send failed for %s: %s", email, e, exc_info=True)
                if cls._console_fallback_allowed():
                    cls._log_to_console(email, code)
                    return
                raise OTPDeliveryError(f"SMTP delivery failed: {e}") from e

        if cls._console_fallback_allowed():
            cls._log_to_console(email, code)
            return

        raise OTPDeliveryError(
            "Email is not configured. Set RESEND_API_KEY and DEFAULT_FROM_EMAIL "
            "(use a from-address on your verified Resend domain), then restart the backend."
        )

    @staticmethod
    def _log_to_console(email: str, code: str):
        """Print OTP to terminal when no email provider is configured (dev only)."""
        print("\n" + "=" * 50, flush=True)
        print(f"  [DEV OTP]  Code for {email}:  {code}", flush=True)
        print("=" * 50 + "\n", flush=True)
        logger.warning("[DEV OTP] Code for %s: %s  (configure Resend to send real emails)", email, code)

