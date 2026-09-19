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

import struct
from PIL import Image, ImageDraw

def _verify_png_bytes(png_bytes: bytes) -> bool:
    if not png_bytes or not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    try:
        with Image.open(io.BytesIO(png_bytes)) as im:
            im.verify()
        return True
    except Exception:
        return False

def _render_emf_vector_to_png(emf_bytes: bytes, width_px: int = 1200, height_px: int = 800) -> bytes:
    if not emf_bytes or len(emf_bytes) < 40:
        return b""

    pos = 0
    total_len = len(emf_bytes)

    rec_type, rec_size = struct.unpack_from("<II", emf_bytes, 0)
    bounds_left, bounds_top, bounds_right, bounds_bottom = 0, 0, 1000, 1000
    if rec_type == 1 and rec_size >= 40:
        rcl_bounds = struct.unpack_from("<iiii", emf_bytes, 8)
        bounds_left, bounds_top, bounds_right, bounds_bottom = rcl_bounds
        
    emf_w = max(10, bounds_right - bounds_left)
    emf_h = max(10, bounds_bottom - bounds_top)

    scale_x = width_px / float(emf_w)
    scale_y = height_px / float(emf_h)

    canvas = Image.new("RGBA", (width_px, height_px), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    current_pen_color = (0, 0, 0, 255)
    current_pen_width = 2
    current_brush_color = (240, 240, 240, 255)

    pos = 0
    while pos + 8 <= total_len:
        rec_type, rec_size = struct.unpack_from("<II", emf_bytes, pos)
        if rec_size < 8 or pos + rec_size > total_len:
            break

        rec_data = emf_bytes[pos : pos + rec_size]

        # Search for embedded DIBs in EMR_STRETCHDIBITS / EMR_BITBLT
        dib_idx = rec_data.find(b"\x28\x00\x00\x00")
        if dib_idx != -1 and dib_idx + 40 <= len(rec_data):
            h_size, w, h, planes, bpp = struct.unpack_from("<IIIHH", rec_data, dib_idx)
            abs_h = abs(h)
            if 0 < w < 8000 and 0 < abs_h < 8000 and bpp in (1, 4, 8, 16, 24, 32):
                dib_bytes = rec_data[dib_idx:]
                colors_used = 0
                if dib_idx + 36 <= len(rec_data):
                    colors_used = struct.unpack_from("<I", rec_data, dib_idx + 32)[0]
                if colors_used == 0 and bpp <= 8:
                    colors_used = 1 << bpp
                off_bits = 14 + h_size + (colors_used * 4)
                bmp_header = struct.pack("<2sIHHI", b"BM", 14 + len(dib_bytes), 0, 0, off_bits)
                try:
                    with Image.open(io.BytesIO(bmp_header + dib_bytes)) as dib_img:
                        dib_rgba = dib_img.convert("RGBA")
                        canvas.paste(dib_rgba, (0, 0), dib_rgba)
                except Exception:
                    pass

        # Render Vector Shapes
        if rec_type in (0x02, 0x03, 0x04):
            if rec_size >= 24:
                l, t, r, b = struct.unpack_from("<iiii", rec_data, 8)
                px_l = int((l - bounds_left) * scale_x)
                px_t = int((t - bounds_top) * scale_y)
                px_r = int((r - bounds_left) * scale_x)
                px_b = int((b - bounds_bottom) * scale_y)
                if rec_type == 0x02:
                    draw.rectangle([px_l, px_t, px_r, px_b], outline=current_pen_color, width=current_pen_width)
                elif rec_type == 0x04:
                    draw.ellipse([px_l, px_t, px_r, px_b], outline=current_pen_color, width=current_pen_width)

        elif rec_type in (0x06, 0x52, 0x53):
            if rec_size >= 28:
                num_pts = struct.unpack_from("<I", rec_data, 24 if rec_type == 0x06 else 20)[0]
                off = 28
                pts = []
                for _ in range(min(num_pts, 500)):
                    if off + 4 <= len(rec_data):
                        x, y = struct.unpack_from("<hh" if rec_type in (0x52, 0x53) else "<ii", rec_data, off)
                        px = int((x - bounds_left) * scale_x)
                        py = int((y - bounds_top) * scale_y)
                        pts.append((px, py))
                        off += 4 if rec_type in (0x52, 0x53) else 8
                if len(pts) >= 2:
                    draw.polygon(pts, outline=current_pen_color, fill=current_brush_color)

        elif rec_type in (0x07, 0x54):
            if rec_size >= 28:
                num_pts = struct.unpack_from("<I", rec_data, 24 if rec_type == 0x07 else 20)[0]
                off = 28
                pts = []
                for _ in range(min(num_pts, 500)):
                    if off + 4 <= len(rec_data):
                        x, y = struct.unpack_from("<hh" if rec_type == 0x54 else "<ii", rec_data, off)
                        px = int((x - bounds_left) * scale_x)
                        py = int((y - bounds_top) * scale_y)
                        pts.append((px, py))
                        off += 4 if rec_type == 0x54 else 8
                if len(pts) >= 2:
                    draw.line(pts, fill=current_pen_color, width=current_pen_width)

        if rec_type == 0x0E:
            break
        pos += rec_size

    out_buf = io.BytesIO()
    canvas.save(out_buf, format="PNG", optimize=True)
    res_png = out_buf.getvalue()
    return res_png if _verify_png_bytes(res_png) else b""

def convert_image_to_latex_compatible(img_bytes: bytes, original_filename_or_ext: str = ".emf") -> Tuple[bytes, str]:
    """
    Converts unsupported image formats (such as EMF/WMF) to a 100% valid LaTeX-compatible PNG format.
    Returns (converted_bytes, target_extension).
    """
    if not img_bytes:
        return img_bytes, original_filename_or_ext

    orig_ext = os.path.splitext(original_filename_or_ext)[1].lower() if "." in original_filename_or_ext else original_filename_or_ext.lower()
    if not orig_ext.startswith("."):
        orig_ext = f".{orig_ext}"

    if orig_ext not in UNSUPPORTED_LATEX_EXTENSIONS:
        return img_bytes, orig_ext

    # 1. Primary Method: Pillow Image.open
    try:
        with Image.open(io.BytesIO(img_bytes)) as pil_img:
            if pil_img.mode not in ("RGB", "RGBA"):
                pil_img = pil_img.convert("RGBA" if "transparency" in pil_img.info or pil_img.mode == "PA" else "RGB")
            out_buffer = io.BytesIO()
            pil_img.save(out_buffer, format="PNG", optimize=True)
            png_bytes = out_buffer.getvalue()
            if _verify_png_bytes(png_bytes):
                logger.info(f"[IMAGE_CONVERT] Successfully converted {orig_ext} image via Pillow ({len(img_bytes)} -> {len(png_bytes)} bytes PNG)")
                return png_bytes, ".png"
    except Exception as pil_err:
        logger.warning(f"[IMAGE_CONVERT_WARNING] Pillow failed to convert {orig_ext} image: {pil_err}")

    # 2. Extract embedded PNG or JPEG raster streams directly from binary bytes
    try:
        png_idx = img_bytes.find(b"\x89PNG\r\n\x1a\n")
        if png_idx != -1:
            iend_idx = img_bytes.find(b"IEND\xaeB`\x82", png_idx)
            if iend_idx != -1:
                extracted_png = img_bytes[png_idx : iend_idx + 8]
                if _verify_png_bytes(extracted_png):
                    logger.info(f"[IMAGE_CONVERT] Extracted embedded PNG from {orig_ext} image ({len(extracted_png)} bytes)")
                    return extracted_png, ".png"

        jpg_idx = img_bytes.find(b"\xff\xd8\xff")
        if jpg_idx != -1:
            eod_idx = img_bytes.find(b"\xff\xd9", jpg_idx)
            if eod_idx != -1:
                extracted_jpg = img_bytes[jpg_idx : eod_idx + 2]
                try:
                    with Image.open(io.BytesIO(extracted_jpg)) as im:
                        out_b = io.BytesIO()
                        im.save(out_b, format="PNG")
                        res_png = out_b.getvalue()
                        if _verify_png_bytes(res_png):
                            logger.info(f"[IMAGE_CONVERT] Converted embedded JPEG to PNG from {orig_ext} image ({len(res_png)} bytes)")
                            return res_png, ".png"
                except Exception:
                    pass
    except Exception as ext_err:
        logger.warning(f"[IMAGE_CONVERT_WARNING] Embedded raster extraction failed: {ext_err}")

    # 3. Vector Render EMF to high-res PNG canvas
    try:
        rendered_png = _render_emf_vector_to_png(img_bytes)
        if _verify_png_bytes(rendered_png):
            logger.info(f"[IMAGE_CONVERT] Rendered vector EMF to PNG ({len(img_bytes)} -> {len(rendered_png)} bytes PNG)")
            return rendered_png, ".png"
    except Exception as vec_err:
        logger.warning(f"[IMAGE_CONVERT_WARNING] Vector EMF rendering failed: {vec_err}")

    # Fallback: Create valid blank RGBA PNG image if all conversions fail (never return raw non-PNG bytes with .png)
    fallback_buf = io.BytesIO()
    fallback_img = Image.new("RGBA", (400, 300), (240, 240, 240, 255))
    fallback_img.save(fallback_buf, format="PNG")
    fallback_bytes = fallback_buf.getvalue()
    logger.error(f"[IMAGE_CONVERT_ERROR] Used valid fallback PNG for unparseable {orig_ext} image")
    return fallback_bytes, ".png"
