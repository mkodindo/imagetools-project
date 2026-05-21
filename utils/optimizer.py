import os

from PIL import Image, ImageOps
from PIL.PngImagePlugin import PngInfo

try:
    import cv2 as _cv2  # noqa: F401
except ImportError:
    pass

_PRESET_QUALITY_MAX = {'speed': 80, 'balanced': 90, 'max': 95}


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

    original_size = os.path.getsize(input_path)

    with Image.open(input_path) as img:
        fmt = img.format  # "JPEG", "PNG", or "WEBP"

        # Capture metadata before any transformation
        exif_bytes = img.info.get('exif', b'')
        png_text   = {k: v for k, v in img.info.items()
                      if isinstance(k, str) and isinstance(v, str)}

        if auto_orient:
            img = ImageOps.exif_transpose(img)

        if fmt == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        elif fmt in ("PNG", "WEBP") and img.mode == "P":
            img = img.convert("RGBA")

        if resize_pct != 100:
            w, h = img.size
            new_w = max(1, round(w * resize_pct / 100))
            new_h = max(1, round(h * resize_pct / 100))
            img = img.resize((new_w, new_h), Image.LANCZOS)

        max_dim = config.get("MAX_DIMENSION")
        if max_dim:
            img = _resize_if_needed(img, max_dim)

        width, height = img.size
        save_kwargs = _build_save_kwargs(fmt, quality, preset)

        if not strip_meta:
            if fmt in ("JPEG", "WEBP") and exif_bytes:
                save_kwargs['exif'] = exif_bytes
            elif fmt == "PNG" and png_text:
                pnginfo = PngInfo()
                for k, v in png_text.items():
                    pnginfo.add_text(k, v)
                save_kwargs['pnginfo'] = pnginfo

        img.save(output_path, format=fmt, **save_kwargs)

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
