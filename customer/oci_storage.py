"""OCI Object Storage helpers for archived WhatsApp images."""

import logging
import mimetypes
from urllib.parse import quote

from milkbasket.secret import (BUCKET_NAME, OCI_FINGERPRINT, OCI_NAMESPACE,
                               OCI_PRIVATE_KEY, OCI_REGION, OCI_TENANCY,
                               OCI_USER, PAR)

logger = logging.getLogger(__name__)


def archive_whatsapp_image(message_id, content, content_type):
    """Store an incoming image and return its object name.

    The message id is unique in WhatsApp, so retrying the webhook safely replaces
    the same object instead of creating duplicate files.
    """
    try:
        import oci
    except ImportError as exc:
        raise RuntimeError('OCI SDK is not installed') from exc

    extension = mimetypes.guess_extension(content_type or '') or ''
    object_name = f'whatsapp/images/{message_id}{extension}'
    config = {
        'user': OCI_USER,
        'fingerprint': OCI_FINGERPRINT,
        'tenancy': OCI_TENANCY,
        'region': OCI_REGION,
        'key_content': OCI_PRIVATE_KEY,
    }
    client = oci.object_storage.ObjectStorageClient(config)
    client.put_object(
        namespace_name=OCI_NAMESPACE,
        bucket_name=BUCKET_NAME,
        object_name=object_name,
        put_object_body=content,
        content_type=content_type or 'application/octet-stream',
    )
    return object_name


def whatsapp_image_par_url(object_name):
    """Return the read-only PAR URL for an archived WhatsApp image."""
    if not object_name:
        return None
    return f"{PAR.rstrip('/')}/{quote(object_name, safe='/')}"
