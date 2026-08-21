import logging
import os
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)

class InvoiceStorageService:
    _PLACEHOLDER_VALUES = {'', 'unused', 'changeme', 'your-key', 'your_key'}

    @classmethod
    def _env(cls, key: str) -> str | None:
        value = (os.environ.get(key) or '').strip()
        if not value or value.lower() in cls._PLACEHOLDER_VALUES:
            return None
        return value

    @classmethod
    def _r2_config(cls):
        return (
            cls._env('R2_ACCESS_KEY_ID'),
            cls._env('R2_SECRET_ACCESS_KEY'),
            cls._env('R2_BUCKET_NAME'),
            cls._env('R2_ENDPOINT_URL'),
        )

    @classmethod
    def upload_invoice(cls, file_obj, firm_id: int) -> str:
        """
        Uploads invoice file to Cloudflare R2, falling back to local Django media storage
        if credentials are not present in the environment.
        R2 Path format: firms/{firm_id}/invoices/raw/{uuid}_{filename}
        """
        filename = file_obj.name
        # Sanitize filename
        safe_filename = "".join(c for c in filename if c.isalnum() or c in ['.', '_', '-']).strip()
        unique_filename = f"{uuid.uuid4()}_{safe_filename}"
        r2_key = f"firms/{firm_id}/invoices/raw/{unique_filename}"

        # Fetch environment parameters
        r2_access_key, r2_secret_key, r2_bucket_name, r2_endpoint_url = cls._r2_config()

        if r2_access_key and r2_secret_key and r2_bucket_name and r2_endpoint_url:
            try:
                import boto3
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=r2_access_key,
                    aws_secret_access_key=r2_secret_key,
                    endpoint_url=r2_endpoint_url
                )

                # Upload to R2
                s3_client.upload_fileobj(
                    file_obj,
                    r2_bucket_name,
                    r2_key,
                    ExtraArgs={'ContentType': file_obj.content_type}
                )

                # Construct public url
                # e.g., https://<endpoint_url>/<bucket>/<key>
                public_url = f"{r2_endpoint_url.rstrip('/')}/{r2_bucket_name}/{r2_key}"
                logger.info("Successfully uploaded bill to Cloudflare R2: %s", public_url)
                return public_url

            except ImportError:
                logger.warning("boto3 package not installed. Falling back to local storage.")
            except Exception as e:
                logger.error("Cloudflare R2 upload failed: %s. Falling back to local storage.", e, exc_info=True)

        # FALLBACK: Save locally to media root
        try:
            local_dir = os.path.join(settings.MEDIA_ROOT, 'firms', str(firm_id), 'invoices', 'raw')
            os.makedirs(local_dir, exist_ok=True)
            local_file_path = os.path.join(local_dir, unique_filename)

            with open(local_file_path, 'wb+') as destination:
                if hasattr(file_obj, 'chunks'):
                    for chunk in file_obj.chunks():
                        destination.write(chunk)
                else:
                    file_obj.seek(0)
                    destination.write(file_obj.read())

            # Construct relative media url path
            local_media_url = f"{settings.MEDIA_URL.rstrip('/')}/firms/{firm_id}/invoices/raw/{unique_filename}"
            logger.info("Successfully saved bill locally to: %s", local_file_path)
            return local_media_url

        except Exception as e:
            logger.error("Local storage fallback failed: %s", e, exc_info=True)
            raise RuntimeError("Failed to store invoice file.")

    @classmethod
    def upload_export(cls, file_data: bytes, filename: str, firm_id: int) -> str:
        """
        Uploads Excel export bytes to Cloudflare R2, falling back to local Django media storage.
        R2 Path format: firms/{firm_id}/exports/{uuid}_{filename}
        """
        unique_filename = f"{uuid.uuid4()}_{filename}"
        r2_key = f"firms/{firm_id}/exports/{unique_filename}"

        r2_access_key, r2_secret_key, r2_bucket_name, r2_endpoint_url = cls._r2_config()

        if r2_access_key and r2_secret_key and r2_bucket_name and r2_endpoint_url:
            try:
                import boto3
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=r2_access_key,
                    aws_secret_access_key=r2_secret_key,
                    endpoint_url=r2_endpoint_url
                )
                s3_client.put_object(
                    Body=file_data,
                    Bucket=r2_bucket_name,
                    Key=r2_key,
                    ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                public_url = f"{r2_endpoint_url.rstrip('/')}/{r2_bucket_name}/{r2_key}"
                logger.info("Successfully uploaded export to Cloudflare R2: %s", public_url)
                return public_url
            except ImportError:
                logger.warning("boto3 package not installed. Falling back to local storage.")
            except Exception as e:
                logger.error("Cloudflare R2 export upload failed: %s. Falling back to local storage.", e, exc_info=True)

        # Fallback: save to media root under exports
        try:
            local_dir = os.path.join(settings.MEDIA_ROOT, 'firms', str(firm_id), 'exports')
            os.makedirs(local_dir, exist_ok=True)
            local_file_path = os.path.join(local_dir, unique_filename)

            with open(local_file_path, 'wb') as destination:
                destination.write(file_data)

            local_media_url = f"{settings.MEDIA_URL.rstrip('/')}/firms/{firm_id}/exports/{unique_filename}"
            logger.info("Successfully saved export locally to: %s", local_file_path)
            return local_media_url
        except Exception as e:
            logger.error("Local export storage fallback failed: %s", e, exc_info=True)
            raise RuntimeError("Failed to store export file.")

    @classmethod
    def read_file_bytes(cls, file_url: str) -> bytes:
        """
        Load stored file bytes from local media path or remote/R2 URL.
        """
        if not file_url:
            raise FileNotFoundError('Empty file URL.')

        media_url = settings.MEDIA_URL.rstrip('/') + '/'
        if file_url.startswith(media_url) or file_url.startswith('/media/'):
            relative = file_url.split('/media/', 1)[-1].lstrip('/')
            local_path = os.path.join(settings.MEDIA_ROOT, *relative.split('/'))
            if not os.path.isfile(local_path):
                raise FileNotFoundError(f'Local media file missing: {local_path}')
            with open(local_path, 'rb') as handle:
                return handle.read()

        r2_access_key, r2_secret_key, r2_bucket_name, r2_endpoint_url = cls._r2_config()
        if (
            r2_access_key
            and r2_secret_key
            and r2_bucket_name
            and r2_endpoint_url
            and r2_endpoint_url.rstrip('/') in file_url
        ):
            # file_url format: {endpoint}/{bucket}/{key}
            prefix = f"{r2_endpoint_url.rstrip('/')}/{r2_bucket_name}/"
            if file_url.startswith(prefix):
                key = file_url[len(prefix):]
                import boto3
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=r2_access_key,
                    aws_secret_access_key=r2_secret_key,
                    endpoint_url=r2_endpoint_url,
                )
                obj = s3_client.get_object(Bucket=r2_bucket_name, Key=key)
                return obj['Body'].read()

        # Last resort: HTTP fetch for absolute URLs
        if file_url.startswith('http://') or file_url.startswith('https://'):
            from urllib.request import urlopen
            with urlopen(file_url, timeout=30) as response:
                return response.read()

        raise FileNotFoundError(f'Unable to resolve file URL: {file_url}')
