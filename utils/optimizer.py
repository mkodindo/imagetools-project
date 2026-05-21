import os

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from PIL.PngImagePlugin import PngInfo

try:
    import cv2 as _cv2  # noqa: F401
except ImportError:
    pass

_PRESET_QUALITY_MAX = {'speed': 80, 'balanced': 90, 'max': 95}
_FMT_TO_EXT = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}


def optimize_image(input_path: str, output_path: str, config, opts: dict | None = None) -> dict:
    """Open input_path, apply opts, compress, write to output_path.

    opts keys: quality (1-95), resize_pct (10-200), strip_metadata (bool),
               auto_orient (bool), preset ('speed'|'balanced'|'max').
    Returns stats: original_size, optimized_size, savings_pct, width, height.
    """
    if opts is None:
        opts = {}

    quality     = max(1, min(95, int(opts.get('quality', 85))))
    resize_pct  = max(10, min(200, int(opts.get('resize_pct', 100))))
    strip_meta  = bool(opts.get('strip_metadata', True))
    auto_orient = bool(opts.get('auto_orient', True))
    preset      = opts.get('preset', 'balanced')
    if preset not in _PRESET_QUALITY_MAX:
        preset = 'balanced'
    quality = min(quality, _PRESET_QUALITY_MAX[preset])

    sharpness  = max(0, min(200, int(opts.get('sharpness',  100))))
    contrast   = max(0, min(200, int(opts.get('contrast',   100))))
    brightness = max(0, min(200, int(opts.get('brightness', 100))))
    blur       = max(0, min(10,  int(opts.get('blur', 0))))
    target_fmt = opts.get('target_format', '').upper()
    if target_fmt not in ('', 'JPEG', 'PNG', 'WEBP'):
        target_fmt = ''

    original_size = os.path.getsize(input_path)

    with Image.open(input_path) as img:
        fmt = img.format  # "JPEG", "PNG", or "WEBP"
        output_fmt = target_fmt if target_fmt else fmt
        output_ext = _FMT_TO_EXT.get(output_fmt, 'jpg')

        # Capture metadata before any transformation
        exif_bytes = img.info.get('exif', b'')
        png_text   = {k: v for k, v in img.info.items()
                      if isinstance(k, str) and isinstance(v, str)}

        if auto_orient:
            img = ImageOps.exif_transpose(img)

        if output_fmt == "JPEG":
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
        elif output_fmt in ("PNG", "WEBP") and img.mode == "P":
            img = img.convert("RGBA")

        if sharpness != 100:
            img = ImageEnhance.Sharpness(img).enhance(sharpness / 100)
        if contrast != 100:
            img = ImageEnhance.Contrast(img).enhance(contrast / 100)
        if brightness != 100:
            img = ImageEnhance.Brightness(img).enhance(brightness / 100)
        if blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur))

        if resize_pct != 100:
            w, h = img.size
            new_w = max(1, round(w * resize_pct / 100))
            new_h = max(1, round(h * resize_pct / 100))
            img = img.resize((new_w, new_h), Image.LANCZOS)

        max_dim = config.get("MAX_DIMENSION")
        if max_dim:
            img = _resize_if_needed(img, max_dim)

        width, height = img.size
        save_kwargs = _build_save_kwargs(output_fmt, quality, preset)

        if not strip_meta:
            if output_fmt in ("JPEG", "WEBP") and exif_bytes:
                save_kwargs['exif'] = exif_bytes
            elif output_fmt == "PNG" and png_text:
                pnginfo = PngInfo()
                for k, v in png_text.items():
                    pnginfo.add_text(k, v)
                save_kwargs['pnginfo'] = pnginfo

        img.save(output_path, format=output_fmt, **save_kwargs)

    optimized_size = os.path.getsize(output_path)
    savings_pct = (
        round((1 - optimized_size / original_size) * 100, 1) if original_size else 0.0
    )

    return {
        "original_size":  original_size,
        "optimized_size": optimized_size,
        "savings_pct":    savings_pct,
        "width":          width,
        "height":         height,
        "output_ext":     output_ext,
    }


def _resize_if_needed(img: Image.Image, max_dim: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_dim:
        return img
    if w >= h:
        new_w, new_h = max_dim, int(h * max_dim / w)
    else:
        new_w, new_h = int(w * max_dim / h), max_dim
    return img.resize((new_w, new_h), Image.LANCZOS)


def _build_save_kwargs(fmt: str, quality: int, preset: str) -> dict:
    if fmt == "JPEG":
        base = {'quality': quality, 'subsampling': 0 if preset == 'max' else 2}
        if preset == 'speed':
            base.update({'optimize': False, 'progressive': False})
        else:
            base.update({'optimize': True, 'progressive': True})
        return base

    if fmt == "PNG":
        level = {'speed': 1, 'balanced': 6, 'max': 9}.get(preset, 6)
        return {'optimize': True, 'compress_level': level}

    if fmt == "WEBP":
        method = {'speed': 0, 'balanced': 4, 'max': 6}.get(preset, 4)
        return {'quality': quality, 'method': method}

    return {}
