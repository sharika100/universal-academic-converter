import os
import io
import logging
from typing import Tuple
from PIL import Image

logger = logging.getLogger("BookImageConverter")

UNSUPPORTED_LATEX_EXTENSIONS = {".emf", ".wmf", ".tif", ".tiff", ".bmp"}

def is_unsupported_latex_image(filename_or_ext: str) -> bool:
    if not filename_or_ext:
        return False
    if filename_or_ext.startswith("."):
        ext = filename_or_ext.lower()
    else:
        ext = os.path.splitext(filename_or_ext)[1].lower()
    return ext in UNSUPPORTED_LATEX_EXTENSIONS

def get_latex_compatible_filename(filename: str) -> str:
    if not filename:
        return filename
    if filename.startswith("."):
        ext = filename.lower()
        if ext in UNSUPPORTED_LATEX_EXTENSIONS:
            return ".png"
        return filename
    base, ext = os.path.splitext(filename)
    if ext.lower() in UNSUPPORTED_LATEX_EXTENSIONS:
        return f"{base}.png"
    return filename

def convert_image_to_latex_compatible(img_bytes: bytes, original_filename_or_ext: str = ".emf") -> Tuple[bytes, str]:
    """
    Converts unsupported image formats (such as EMF/WMF) to a LaTeX-compatible PNG format.
    Returns (converted_bytes, target_extension).
    """
    if not img_bytes:
        return img_bytes, original_filename_or_ext

    orig_ext = os.path.splitext(original_filename_or_ext)[1].lower() if "." in original_filename_or_ext else original_filename_or_ext.lower()
    if not orig_ext.startswith("."):
        orig_ext = f".{orig_ext}"

    if orig_ext not in UNSUPPORTED_LATEX_EXTENSIONS:
        return img_bytes, orig_ext

    # 1. Primary Method: Pillow Image.open (supports EMF / WMF / BMP / TIFF)
    try:
        with Image.open(io.BytesIO(img_bytes)) as pil_img:
            # Convert to RGB or RGBA mode if necessary
            if pil_img.mode not in ("RGB", "RGBA"):
                pil_img = pil_img.convert("RGBA" if "transparency" in pil_img.info or pil_img.mode == "PA" else "RGB")
            
            out_buffer = io.BytesIO()
            pil_img.save(out_buffer, format="PNG", optimize=True)
            png_bytes = out_buffer.getvalue()
            logger.info(f"[IMAGE_CONVERT] Successfully converted {orig_ext} image ({len(img_bytes)} bytes -> {len(png_bytes)} bytes PNG)")
            return png_bytes, ".png"
    except Exception as pil_err:
        logger.warning(f"[IMAGE_CONVERT_WARNING] Pillow failed to convert {orig_ext} image: {pil_err}")

    # 2. Fallback Method: Extract embedded PNG or JPEG raster streams directly from binary bytes
    try:
        png_idx = img_bytes.find(b"\x89PNG\r\n\x1a\n")
        if png_idx != -1:
            iend_idx = img_bytes.find(b"IEND\xaeB`\x82", png_idx)
            if iend_idx != -1:
                extracted_png = img_bytes[png_idx : iend_idx + 8]
                logger.info(f"[IMAGE_CONVERT] Extracted embedded PNG from {orig_ext} image ({len(extracted_png)} bytes)")
                return extracted_png, ".png"

        jpg_idx = img_bytes.find(b"\xff\xd8\xff")
        if jpg_idx != -1:
            eod_idx = img_bytes.find(b"\xff\xd9", jpg_idx)
            if eod_idx != -1:
                extracted_jpg = img_bytes[jpg_idx : eod_idx + 2]
                logger.info(f"[IMAGE_CONVERT] Extracted embedded JPEG from {orig_ext} image ({len(extracted_jpg)} bytes)")
                return extracted_jpg, ".jpg"
    except Exception as ext_err:
        logger.warning(f"[IMAGE_CONVERT_WARNING] Embedded raster extraction failed: {ext_err}")

    # Return original bytes if all conversion attempts fail
    return img_bytes, orig_ext
