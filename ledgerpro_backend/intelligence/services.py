"""
Storage service for intelligence documents — same R2/local pattern as
``invoices.services.InvoiceStorageService``.
"""
import logging
import os
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)


class DocumentStorageService:
    @classmethod
    def upload_document(cls, file_obj, firm_id: int, doc_type: str) -> str:
        filename = file_obj.name
        safe_filename = ''.join(
            c for c in filename if c.isalnum() or c in ('.', '_', '-')
        ).strip()
        unique_filename = f"{uuid.uuid4()}_{safe_filename}"
        r2_key = f"firms/{firm_id}/documents/{doc_type}/{unique_filename}"

        r2_access_key = os.environ.get('R2_ACCESS_KEY_ID')
        r2_secret_key = os.environ.get('R2_SECRET_ACCESS_KEY')
        r2_bucket_name = os.environ.get('R2_BUCKET_NAME')
        r2_endpoint_url = os.environ.get('R2_ENDPOINT_URL')

        if r2_access_key and r2_secret_key and r2_bucket_name and r2_endpoint_url:
            try:
                import boto3
                s3 = boto3.client(
                    's3',
                    aws_access_key_id=r2_access_key,
                    aws_secret_access_key=r2_secret_key,
                    endpoint_url=r2_endpoint_url,
                )
                s3.upload_fileobj(
                    file_obj, r2_bucket_name, r2_key,
                    ExtraArgs={'ContentType': getattr(file_obj, 'content_type', 'application/octet-stream')},
                )
                public_url = f"{r2_endpoint_url.rstrip('/')}/{r2_bucket_name}/{r2_key}"
                logger.info("Uploaded document to R2: %s", public_url)
                return public_url
            except ImportError:
                logger.warning("boto3 not installed, falling back to local storage.")
            except Exception as exc:
                logger.error("R2 upload failed: %s. Using local storage.", exc, exc_info=True)

        # Local fallback
        local_dir = os.path.join(
            settings.MEDIA_ROOT, 'firms', str(firm_id), 'documents', doc_type,
        )
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, unique_filename)

        with open(local_path, 'wb+') as dest:
            if hasattr(file_obj, 'chunks'):
                for chunk in file_obj.chunks():
                    dest.write(chunk)
            else:
                file_obj.seek(0)
                dest.write(file_obj.read())

        media_url = (
            f"{settings.MEDIA_URL.rstrip('/')}/firms/{firm_id}"
            f"/documents/{doc_type}/{unique_filename}"
        )
        logger.info("Saved document locally: %s", local_path)
        return media_url
