import os
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request

from poem_reciter.models import EvaluationResult
from poem_reciter.repository import FilePoemRepository, PoemRepository, extract_poem_chars
from poem_reciter.service import ReciterService
from poem_reciter.storage import StatsStore

DEFAULT_POEMS_PATH = Path(__file__).resolve().parent.parent / "Poems"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "poem_reciter.db"


def create_app(
    poems_path: Optional[str | Path] = None,
    repository: Optional[PoemRepository] = None,
    db_path: Optional[str | Path] = None,
    stats_store: Optional[StatsStore] = None,
) -> Flask:
    """Flask application factory."""
    app = Flask(__name__)

    if repository is None:
        resolved_path = poems_path or os.environ.get("POEMS_FILE_PATH", DEFAULT_POEMS_PATH)
        repository = FilePoemRepository(resolved_path)

    service = ReciterService(repository)
    app.config["RECITER_SERVICE"] = service

    explicit_store: Optional[StatsStore] = stats_store
    if explicit_store is None and db_path is not None:
        explicit_store = StatsStore(db_path)
        explicit_store.sync_poems(service.get_all_poems())

    lazy_store_cache: dict[str, StatsStore] = {}
    last_recorded_stats: dict[int, dict] = {}

    def get_store() -> StatsStore:
        if explicit_store is not None:
            return explicit_store
        mode = "testing" if app.config.get("TESTING") else "default"
        if mode not in lazy_store_cache:
            target_db = (
                ":memory:"
                if mode == "testing"
                else os.environ.get("POEM_RECITER_DB_PATH", DEFAULT_DB_PATH)
            )
            store = StatsStore(target_db)
            store.sync_poems(service.get_all_poems())
            lazy_store_cache[mode] = store
            app.config["STATS_STORE"] = store
        return lazy_store_cache[mode]

    if explicit_store is not None:
        app.config["STATS_STORE"] = explicit_store

    def _on_attempt(result: EvaluationResult) -> None:
        store = get_store()
        last_recorded_stats[result.poem_id] = store.record_attempt(result)

    service.register_attempt_listener(_on_attempt)

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
        data = poem.to_prompt_dict()
        data["char_count"] = len(extract_poem_chars(poem.text))
        data["poem_stats"] = get_store().get_poem_stats(poem.header)
        return jsonify(data)

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

        response_data = result.to_dict()
        poem_stats = last_recorded_stats.get(poem_id) or get_store().get_poem_stats(result.header)
        if poem_stats is not None:
            response_data["poem_stats"] = poem_stats
        return jsonify(response_data)

    @app.get("/api/stats")
    def get_stats():
        group_by = request.args.get("group_by", "poem").strip().lower()
        if group_by not in ("poem", "author", "dynasty"):
            return (
                jsonify({"error": "Invalid 'group_by' parameter; must be 'poem', 'author', or 'dynasty'."}),
                400,
            )

        recited_only_raw = request.args.get("recited_only", "false").strip().lower()
        recited_only = recited_only_raw in ("1", "true", "yes")

        stats = get_store().get_aggregated_stats(group_by=group_by, recited_only=recited_only)
        return jsonify(stats)

    return app

