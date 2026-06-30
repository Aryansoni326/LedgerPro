import hashlib
import hmac
import json
import logging
import secrets
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


class OTPService:
    @staticmethod
    def generate_otp() -> str:
        """Generate a cryptographically secure 4-digit code."""
        return "".join(secrets.choice("0123456789") for _ in range(4))

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
        """Send the OTP code via Resend or log to console in dev mode."""
        subject = "LedgerPro v2 - Your 2FA Verification Code"
        html_content = f"""
        <html>
        <body style="font-family: sans-serif; background-color: #ffffff; color: #111111; padding: 40px; text-align: center;">
            <div style="max-width: 500px; margin: 0 auto; border: 1px solid #e5e5e5; padding: 40px; border-radius: 8px;">
                <h2 style="font-size: 24px; font-weight: bold; margin-bottom: 24px; color: #000000;">LedgerPro 2FA Code</h2>
                <p style="font-size: 16px; color: #666666; margin-bottom: 32px;">Please enter the following 4-digit code to log in to your account. This code is valid for 5 minutes.</p>
                <div style="font-size: 36px; font-weight: bold; letter-spacing: 6px; padding: 16px 32px; background-color: #f9f9f9; border: 1px solid #e5e5e5; border-radius: 4px; display: inline-block; margin-bottom: 32px; color: #000000;">
                    {code}
                </div>
                <p style="font-size: 12px; color: #999999; margin-top: 20px;">If you did not request this login code, you can safely ignore this email.</p>
            </div>
        </body>
        </html>
        """

        resend_key = getattr(settings, "RESEND_API_KEY", None)
        has_resend = resend_key and "mock" not in resend_key and "your_resend" not in resend_key

        if has_resend:
            try:
                url = "https://api.resend.com/emails"
                headers = {
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "from": "LedgerPro Auth <onboarding@resend.dev>",
                    "to": [email],
                    "subject": subject,
                    "html": html_content
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers=headers,
                    method='POST'
                )
                with urllib.request.urlopen(req):
                    logger.info("OTP email successfully sent to %s via Resend API.", email)
            except Exception as e:
                logger.error("Failed to send email via Resend API: %s. Falling back to console logging.", e)
                cls._log_to_console(email, code)
        else:
            cls._log_to_console(email, code)

    @staticmethod
    def _log_to_console(email: str, code: str):
        """Helper to print the OTP code to terminal."""
        print("\n========================================", flush=True)
        print(f"[DEVELOPMENT OTP] Code for {email} is: {code}", flush=True)
        print("========================================\n", flush=True)
        logger.warning(f"[DEVELOPMENT OTP] Code for {email} is: {code}")
