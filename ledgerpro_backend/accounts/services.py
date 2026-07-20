import hashlib
import hmac
import json
import logging
import secrets
import urllib.parse
import urllib.request

from django.conf import settings

from .models import OTPVerification, User

logger = logging.getLogger(__name__)

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

    @classmethod
    def send_otp_email(cls, email: str, code: str):
        """
        Send the OTP code via Django SMTP.
        Falls back to console logging only when EMAIL_HOST / EMAIL_HOST_USER are not set
        (i.e. in development without SMTP credentials).
        """
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
                raise RuntimeError(f"Failed to send OTP email via SMTP: {e}") from e

        # Dev-only fallback — no SMTP configured
        cls._log_to_console(email, code)

    @staticmethod
    def _log_to_console(email: str, code: str):
        """Print OTP to terminal when SMTP is not configured (development only)."""
        print("\n" + "=" * 50, flush=True)
        print(f"  [DEV OTP]  Code for {email}:  {code}", flush=True)
        print("=" * 50 + "\n", flush=True)
        logger.warning("[DEV OTP] Code for %s: %s  (configure SMTP to send real emails)", email, code)

