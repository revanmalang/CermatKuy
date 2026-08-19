"""CermatKuy - Flask application entry point.

Responsible only for: app configuration, routing, request validation and
JSON response shaping. All analysis logic lives under services/.
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request

from services.analyzer import analyze_content
from services.article_extractor import ArticleExtractionError, extract_article
from services.fact_checker import search_fact_checks
from services.source_checker import check_domain
from utils.text_utils import (
    MAX_TEXT_LENGTH,
    MIN_TEXT_LENGTH,
    clean_whitespace,
    count_words,
    is_valid_http_url,
    truncate,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024  # 512 KB max request body
app.config["JSON_SORT_KEYS"] = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cermatkuy")


def _error_response(message: str, status_code: int = 400):
    return jsonify({"success": False, "message": message}), status_code


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return _error_response("Request tidak valid. Pastikan mengirim data JSON.")

    input_type = payload.get("type")
    content = payload.get("content")

    if input_type not in ("text", "url"):
        return _error_response("Parameter 'type' harus bernilai 'text' atau 'url'.")
    if not content or not isinstance(content, str) or not content.strip():
        return _error_response("Konten tidak boleh kosong.")

    content = content.strip()

    try:
        if input_type == "url":
            return _analyze_url(content)
        return _analyze_text(content)
    except ArticleExtractionError as exc:
        return _error_response(str(exc))
    except Exception:  # noqa: BLE001 - never leak internal tracebacks to the client
        logger.exception("Unexpected error during analysis")
        return _error_response("Terjadi kesalahan saat menganalisis konten. Silakan coba lagi.", 500)


def _analyze_text(raw_text: str):
    if len(raw_text) < MIN_TEXT_LENGTH:
        return _error_response(f"Teks terlalu pendek. Minimal {MIN_TEXT_LENGTH} karakter.")

    text = clean_whitespace(truncate(raw_text, MAX_TEXT_LENGTH))

    source_info = check_domain("")
    fact_check_info = search_fact_checks(text[:200])
    result = analyze_content(text, source_info, fact_check_info)

    response = _build_response(result, article=None)
    return jsonify(response)


def _analyze_url(url: str):
    if not is_valid_http_url(url):
        return _error_response("URL tidak valid. Gunakan format http:// atau https://")

    article = extract_article(url)
    text = clean_whitespace(truncate(article["content"], MAX_TEXT_LENGTH))

    if len(text) < MIN_TEXT_LENGTH:
        return _error_response(
            "Konten artikel terlalu pendek untuk dianalisis. Silakan tempel isi berita secara langsung."
        )

    source_info = check_domain(article["domain"])
    fact_check_query = article["title"] or text[:200]
    fact_check_info = search_fact_checks(fact_check_query)
    result = analyze_content(text, source_info, fact_check_info)

    article_summary = {
        "title": article["title"],
        "domain": article["domain"],
        "url": article["url"],
        "word_count": count_words(text),
    }
    response = _build_response(result, article=article_summary)
    return jsonify(response)


def _build_response(result: dict, article: dict | None) -> dict:
    return {
        "success": True,
        "score": result["score"],
        "status": result["status"],
        "summary": result["summary"],
        "indicators": result["indicators"],
        "positive_indicators": result["positive_indicators"],
        "risk_indicators": result["risk_indicators"],
        "recommendation": result["recommendation"],
        "score_breakdown": result["score_breakdown"],
        "article": article,
    }


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return _error_response("Endpoint tidak ditemukan.", 404)
    return render_template("error.html", code=404, message="Halaman tidak ditemukan."), 404


@app.errorhandler(413)
def payload_too_large(_error):
    return _error_response("Ukuran request terlalu besar.", 413)


@app.errorhandler(500)
def server_error(_error):
    if request.path.startswith("/api/"):
        return _error_response("Terjadi kesalahan pada server.", 500)
    return render_template("error.html", code=500, message="Terjadi kesalahan pada server."), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
