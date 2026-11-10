"""
Image upload helpers shared by profiles and listings:
validate type + size, then resize with Pillow and store as JPEG.
"""
import io
import uuid

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_file(f):
    max_mb = settings.CHEERIPICK["MAX_UPLOAD_MB"]
    if f.size > max_mb * 1024 * 1024:
        raise ValidationError(f"That photo is over {max_mb} MB — try a smaller one.")
    try:
        f.seek(0)
        img = Image.open(f)
        fmt = img.format
        img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValidationError("That doesn't look like an image we can read.")
    finally:
        f.seek(0)
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError("Only JPG, PNG or WEBP please.")


def process_image(f, max_px=None):
    """Return a resized JPEG upload ready to assign to an ImageField."""
    max_px = max_px or settings.CHEERIPICK["IMAGE_MAX_PX"]
    f.seek(0)
    img = Image.open(f)
    img = ImageOps.exif_transpose(img)  # respect phone orientation
    if img.mode not in ("RGB", "L"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1])
        else:
            background.paste(img.convert("RGB"))
        img = background
    elif img.mode == "L":
        img = img.convert("RGB")
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    buf.seek(0)
    name = f"{uuid.uuid4().hex[:16]}.jpg"
    return InMemoryUploadedFile(buf, "image", name, "image/jpeg", buf.getbuffer().nbytes, None)


# --- Multiple-file upload field (pattern from the Django docs) --------------
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}))
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        cleaned = []
        errors = []
        for f in files:
            try:
                f = super().clean(f, initial)
                validate_image_file(f)
                cleaned.append(f)
            except ValidationError as e:
                errors.extend(e.messages)
        if errors:
            raise ValidationError(errors)
        return cleaned
