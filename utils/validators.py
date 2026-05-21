import magic

MIME_TO_EXT = {
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
    "image/webp": {"webp"},
}


def validate_upload(file_storage, config) -> str | None:
    """Returns an error string on failure, None on success.

    Validation order:
      1. Size  (seek-to-end; Flask 413 is primary gate, this is defence-in-depth)
      2. Extension
      3. MIME via libmagic (reads first 261 bytes — immune to extension spoofing)
      4. Cross-check MIME vs extension
    """
    file_storage.seek(0, 2)
    size = file_storage.tell()
    file_storage.seek(0)

    if size > config["MAX_CONTENT_LENGTH"]:
        return "File exceeds 25 MB limit"
    if size == 0:
        return "File is empty"

    filename = file_storage.filename or ""
    if "." not in filename:
        return "File has no extension"
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in config["ALLOWED_EXTENSIONS"]:
        return f"Extension '.{ext}' is not allowed. Accepted: jpg, jpeg, png, webp"

    header = file_storage.read(261)
    file_storage.seek(0)
    mime = magic.from_buffer(header, mime=True)

    if mime not in config["ALLOWED_MIME_TYPES"]:
        return f"File content detected as '{mime}', which is not allowed"

    allowed_exts_for_mime = MIME_TO_EXT.get(mime, set())
    if ext not in allowed_exts_for_mime:
        return f"Extension '.{ext}' does not match detected MIME type '{mime}'"

    return None
