import logging
import os
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)


class TradeDocStorageService:
    @classmethod
    def upload_trade_doc(cls, file_obj, firm_id: int) -> str:
        """
        Uploads a Bill of Entry / Shipping Bill file to Cloudflare R2,
        falling back to local Django media storage if credentials are absent.
        R2 Path: firms/{firm_id}/import_export/raw/{uuid}_{filename}
        """
        filename = file_obj.name
        safe_filename = "".join(c for c in filename if c.isalnum() or c in ['.', '_', '-']).strip()
        unique_filename = f"{uuid.uuid4()}_{safe_filename}"
        r2_key = f"firms/{firm_id}/import_export/raw/{unique_filename}"

        r2_access_key = os.environ.get('R2_ACCESS_KEY_ID')
        r2_secret_key = os.environ.get('R2_SECRET_ACCESS_KEY')
        r2_bucket_name = os.environ.get('R2_BUCKET_NAME')
        r2_endpoint_url = os.environ.get('R2_ENDPOINT_URL')

        if r2_access_key and r2_secret_key and r2_bucket_name and r2_endpoint_url:
            try:
                import boto3
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=r2_access_key,
                    aws_secret_access_key=r2_secret_key,
                    endpoint_url=r2_endpoint_url
                )
                s3_client.upload_fileobj(
                    file_obj,
                    r2_bucket_name,
                    r2_key,
                    ExtraArgs={'ContentType': getattr(file_obj, 'content_type', 'application/octet-stream')}
                )
                public_url = f"{r2_endpoint_url.rstrip('/')}/{r2_bucket_name}/{r2_key}"
                logger.info("Uploaded trade doc to R2: %s", public_url)
                return public_url
            except ImportError:
                logger.warning("boto3 not installed. Falling back to local storage.")
            except Exception as e:
                logger.error("R2 upload failed: %s. Falling back to local storage.", e)

        # Fallback: local media storage
        try:
            local_dir = os.path.join(settings.MEDIA_ROOT, 'firms', str(firm_id), 'import_export', 'raw')
            os.makedirs(local_dir, exist_ok=True)
            local_file_path = os.path.join(local_dir, unique_filename)

            with open(local_file_path, 'wb+') as destination:
                if hasattr(file_obj, 'chunks'):
                    for chunk in file_obj.chunks():
                        destination.write(chunk)
                else:
                    file_obj.seek(0)
                    destination.write(file_obj.read())

            local_media_url = f"{settings.MEDIA_URL.rstrip('/')}/firms/{firm_id}/import_export/raw/{unique_filename}"
            logger.info("Saved trade doc locally: %s", local_file_path)
            return local_media_url
        except Exception as e:
            logger.error("Local storage fallback failed: %s", e, exc_info=True)
            raise RuntimeError("Failed to store trade document file.")
