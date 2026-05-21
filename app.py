import os
import shutil
import uuid

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
from utils.cleaner import start_cleaner
from utils.optimizer import optimize_image
from utils.validators import validate_upload

_VALID_PRESETS = {'speed', 'balanced', 'max'}


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[app.config["RATELIMIT_DEFAULT"]],
        storage_uri=app.config["RATELIMIT_STORAGE_URI"],
    )

    start_cleaner(app.config["UPLOAD_FOLDER"], app.config["TEMP_TTL"])

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/upload", methods=["POST"])
    @limiter.limit(app.config["RATELIMIT_UPLOAD"])
    def upload():
        file = request.files.get("image")
        if not file:
            return jsonify(error="No file provided"), 400

        error = validate_upload(file, app.config)
        if error:
            return jsonify(error=error), 422

        # Parse and sanitize user options
        try:
            quality = max(1, min(95, int(request.form.get('quality', 85))))
        except (TypeError, ValueError):
            quality = 85

        try:
            resize_pct = max(10, min(200, int(request.form.get('resize_pct', 100))))
        except (TypeError, ValueError):
            resize_pct = 100

        strip_metadata = request.form.get('strip_metadata', 'true') == 'true'
        auto_orient    = request.form.get('auto_orient', 'true') == 'true'
        preset         = request.form.get('preset', 'balanced')
        if preset not in _VALID_PRESETS:
            preset = 'balanced'

        try:
            sharpness = max(0, min(200, int(request.form.get('sharpness', 100))))
        except (TypeError, ValueError):
            sharpness = 100
        try:
            contrast = max(0, min(200, int(request.form.get('contrast', 100))))
        except (TypeError, ValueError):
            contrast = 100
        try:
            brightness = max(0, min(200, int(request.form.get('brightness', 100))))
        except (TypeError, ValueError):
            brightness = 100
        try:
            blur = max(0, min(10, int(request.form.get('blur', 0))))
        except (TypeError, ValueError):
            blur = 0

        _VALID_FORMATS = {'', 'jpeg', 'png', 'webp'}
        target_format = request.form.get('target_format', '').lower()
        if target_format not in _VALID_FORMATS:
            target_format = ''
        target_fmt_upper = {'jpeg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP'}.get(target_format, '')

        opts = {
            'quality':        quality,
            'resize_pct':     resize_pct,
            'strip_metadata': strip_metadata,
            'auto_orient':    auto_orient,
            'preset':         preset,
            'sharpness':      sharpness,
            'contrast':       contrast,
            'brightness':     brightness,
            'blur':           blur,
            'target_format':  target_fmt_upper,
        }

        session_id = uuid.uuid4().hex
        session_dir = os.path.join(app.config["UPLOAD_FOLDER"], session_id)
        os.makedirs(session_dir, exist_ok=True)

        ext = file.filename.rsplit(".", 1)[-1].lower()
        original_path     = os.path.join(session_dir, f"original.{ext}")
        optimized_path_tmp = os.path.join(session_dir, f"optimized.{ext}")
        file.save(original_path)

        stats = optimize_image(original_path, optimized_path_tmp, app.config, opts)

        output_ext = stats["output_ext"]
        optimized_path_final = os.path.join(session_dir, f"optimized.{output_ext}")
        if optimized_path_tmp != optimized_path_final:
            os.rename(optimized_path_tmp, optimized_path_final)

        return jsonify(
            session_id=session_id,
            original_size=stats["original_size"],
            optimized_size=stats["optimized_size"],
            savings_pct=stats["savings_pct"],
            width=stats["width"],
            height=stats["height"],
            output_ext=output_ext,
        )

    @app.route("/preview/<session_id>/<which>")
    def preview(session_id, which):
        if which not in ("original", "optimized"):
            abort(404)
        if not session_id.isalnum() or len(session_id) != 32:
            abort(400)
        folder = os.path.join(app.config["UPLOAD_FOLDER"], session_id)
        for ext in Config.ALLOWED_EXTENSIONS:
            if os.path.exists(os.path.join(folder, f"{which}.{ext}")):
                return send_from_directory(folder, f"{which}.{ext}")
        abort(404)

    @app.route("/session/<session_id>", methods=["DELETE"])
    def delete_session(session_id):
        if not session_id.isalnum() or len(session_id) != 32:
            abort(400)
        folder = os.path.join(app.config["UPLOAD_FOLDER"], session_id)
        shutil.rmtree(folder, ignore_errors=True)
        return '', 204

    @app.errorhandler(413)
    def too_large(e):
        return jsonify(error="File exceeds 25 MB limit"), 413

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify(error="Too many requests — try again in a minute"), 429

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Not found"), 404

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
