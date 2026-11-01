import os
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request

from poem_reciter.repository import FilePoemRepository, PoemRepository
from poem_reciter.service import ReciterService

DEFAULT_POEMS_PATH = Path(__file__).resolve().parent.parent / "Poems"


def create_app(
    poems_path: Optional[str | Path] = None,
    repository: Optional[PoemRepository] = None,
) -> Flask:
    """Flask application factory."""
    app = Flask(__name__)

    if repository is None:
        resolved_path = poems_path or os.environ.get("POEMS_FILE_PATH", DEFAULT_POEMS_PATH)
        repository = FilePoemRepository(resolved_path)

    service = ReciterService(repository)
    app.config["RECITER_SERVICE"] = service

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "total_poems": len(service.get_all_poems()),
            }
        )

    @app.get("/api/poems/random")
    def random_poem():
        exclude_raw = request.args.get("exclude")
        exclude_id: Optional[int] = None
        if exclude_raw is not None:
            try:
                exclude_id = int(exclude_raw)
            except ValueError:
                return jsonify({"error": "Invalid 'exclude' parameter; must be an integer."}), 400

        poem = service.pick_random_poem(exclude_id=exclude_id)
        return jsonify(poem.to_prompt_dict())

    @app.post("/api/poems/<int:poem_id>/check")
    def check_poem(poem_id: int):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or "answer" not in payload:
            return jsonify({"error": "Request JSON must include an 'answer' field."}), 400

        raw_answer = payload.get("answer", "")
        if not isinstance(raw_answer, str):
            return jsonify({"error": "'answer' must be a string."}), 400

        try:
            result = service.evaluate(poem_id, raw_answer)
        except KeyError:
            return jsonify({"error": f"Poem {poem_id} not found."}), 404

        return jsonify(result.to_dict())

    return app

