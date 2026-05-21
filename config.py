import os
import tempfile


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "imagetools")
    TEMP_TTL = 600  # seconds

    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

    RATELIMIT_DEFAULT = "200 per day"
    RATELIMIT_UPLOAD = "30 per minute"
    RATELIMIT_STORAGE_URI = "memory://"

    JPEG_QUALITY = 82
    WEBP_QUALITY = 82
    PNG_COMPRESS = 6
    MAX_DIMENSION = 4096
