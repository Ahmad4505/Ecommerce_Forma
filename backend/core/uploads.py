from io import BytesIO
import uuid
import warnings
from PIL import Image
from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError

def safe_image(upload):
    if upload.size > 2 * 1024 * 1024:
        raise ValidationError('Images must be smaller than 2 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(upload)
            if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValueError()
            if min(image.size) < 32 or max(image.size) > 6000:
                raise ValueError()
            image.verify()
            upload.seek(0)
            image = Image.open(upload).convert('RGB')
            output = BytesIO()
            image.save(output, format='JPEG', quality=90)
            return ContentFile(output.getvalue(), name=f'{uuid.uuid4().hex}.jpg')
    except Exception:
        raise ValidationError('Upload a valid JPEG, PNG or WebP, 32–6000 pixels per side.')
