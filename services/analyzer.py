"""Local heuristic hoax-risk analyzer.

Every number produced here is derived from a measurable property of the
text (keyword matches, punctuation ratios, structural counts) -- nothing
is random and nothing is a black box. See `analyze_content()` for the
final weighted score.

Scoring weights (must sum to 1.0):
    Source Reputation      25%
    Language Pattern       25%
    Sensationalism         20%
    Text Structure         15%
    Fact Check Evidence    15%
"""

from __future__ import annotations

import re

from utils.text_utils import (
    count_exclamations,
    count_paragraphs,
    count_questions,
    count_repeated_punctuation,
    count_sentences,
    count_words,
    uppercase_word_ratio,
)

# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------
WEIGHTS = {
    "source": 0.25,
    "language": 0.25,
    "sensationalism": 0.20,
    "structure": 0.15,
    "fact_check": 0.15,
}

# ---------------------------------------------------------------------------
# Pattern dictionaries (Indonesian hoax/clickbait vernacular)
# ---------------------------------------------------------------------------
SENSATIONAL_PHRASES = [
    "viral", "sebarkan", "sebelum dihapus", "media tidak memberitakan",
    "rahasia", "terbongkar", "wajib share", "bagikan sekarang",
    "darurat", "mengejutkan", "anda harus tahu", "waspada", "geger",
    "heboh", "innalillahi", "astaghfirullah", "tolong sebarkan",
    "share sebanyak banyaknya", "sebelum di hapus", "sebelum di banned",
]

CLICKBAIT_PATTERNS = [
    r"anda (tidak akan|tak akan) percaya",
    r"nomor \d+ (bikin|akan)",
    r"media (menyembunyikan|menutupi)",
    r"sebarkan sebelum terlambat",
    r"fakta yang tidak ingin mereka",
    r"tidak ingin anda tahu",
    r"bikin (geger|heboh|kaget)",
    r"ternyata (begini|seperti ini)",
    r"apa yang terjadi selanjutnya",
]

_COMPILED_CLICKBAIT = [re.compile(p, re.IGNORECASE) for p in CLICKBAIT_PATTERNS]


def detect_sensational_language(text: str) -> dict:
    """Scan for known sensational/hoax-spreading phrases (case-insensitive)."""
    lowered = (text or "").lower()
    matches = [phrase for phrase in SENSATIONAL_PHRASES if phrase in lowered]

    # Each match reduces the language-pattern score. Diminishing penalty
    # after the first few matches so one viral buzzword doesn't dominate
    # the whole score, but repeated use is still clearly penalized.
    score = 100
    for i, _ in enumerate(matches):
        score -= max(25 - i * 4, 8)
    score = max(score, 0)

    return {
        "matches": matches,
        "match_count": len(matches),
        "score": score,
    }


def detect_clickbait(text: str) -> dict:
    matches = []
    for pattern in _COMPILED_CLICKBAIT:
        found = pattern.search(text or "")
        if found:
            matches.append(found.group(0))

    score = 100
    for i, _ in enumerate(matches):
        score -= max(30 - i * 5, 10)
    score = max(score, 0)

    return {
        "matches": matches,
        "match_count": len(matches),
        "score": score,
    }


def analyze_capitalization(text: str) -> dict:
    ratio = uppercase_word_ratio(text)
    if ratio >= 40:
        score = 20
    elif ratio >= 25:
        score = 45
    elif ratio >= 12:
        score = 70
    elif ratio >= 5:
        score = 88
    else:
        score = 100
    return {"uppercase_ratio": ratio, "score": score}


def analyze_punctuation(text: str) -> dict:
    exclamations = count_exclamations(text)
    questions = count_questions(text)
    repeated_runs = count_repeated_punctuation(text)
    words = max(count_words(text), 1)

    exclaim_ratio = exclamations / words * 100

    score = 100
    if repeated_runs > 0:
        score -= min(repeated_runs * 15, 60)
    if exclaim_ratio > 3:
        score -= min((exclaim_ratio - 3) * 6, 30)
    score = max(score, 0)

    return {
        "exclamation_count": exclamations,
        "question_count": questions,
        "repeated_punctuation_runs": repeated_runs,
        "score": score,
    }


def analyze_sensationalism(text: str) -> dict:
    """Combines capitalization + punctuation + clickbait pattern signals."""
    caps = analyze_capitalization(text)
    punct = analyze_punctuation(text)
    clickbait = detect_clickbait(text)

    # Equal-weighted blend of the three sensationalism sub-signals.
    combined = round((caps["score"] + punct["score"] + clickbait["score"]) / 3)

    return {
        "score": combined,
        "capitalization": caps,
        "punctuation": punct,
        "clickbait": clickbait,
    }


def analyze_structure(text: str) -> dict:
    words = count_words(text)
    sentences = count_sentences(text)
    paragraphs = count_paragraphs(text)
    avg_words_per_sentence = round(words / sentences, 1) if sentences else 0.0

    score = 100
    if words < 30:
        score -= 45  # far too short to carry real substance
    elif words < 80:
        score -= 20
    elif words < 150:
        score -= 5

    if sentences <= 1 and words > 30:
        score -= 15  # wall-of-text / no sentence structure

    if avg_words_per_sentence and avg_words_per_sentence > 60:
        score -= 10  # run-on, hard-to-verify structure

    score = max(min(score, 100), 0)

    return {
        "word_count": words,
        "sentence_count": sentences,
        "paragraph_count": paragraphs,
        "avg_words_per_sentence": avg_words_per_sentence,
        "score": score,
    }


def _status_from_score(score: int) -> str:
    if score <= 39:
        return "Kemungkinan Hoaks"
    if score <= 69:
        return "Perlu Verifikasi"
    return "Valid"


def _build_indicators(language: dict, sensationalism: dict, structure: dict, source: dict, fact_check: dict) -> dict:
    """Turn raw sub-analysis results into user-facing indicator lists."""
    indicators = []
    positive = []
    risk = []

    # Source
    if source.get("trusted"):
        indicators.append({"name": "Reputasi sumber", "status": "good", "description": source["description"]})
        positive.append("Sumber berita termasuk daftar yang dikenal")
    elif source.get("domain"):
        indicators.append({"name": "Reputasi sumber", "status": "neutral", "description": source["description"]})
        risk.append("Reputasi domain belum teridentifikasi sistem")
    else:
        indicators.append({"name": "Reputasi sumber", "status": "neutral", "description": source["description"]})

    # Language pattern
    if language["match_count"] > 0:
        phrase_list = ", ".join(language["matches"][:5])
        indicators.append({
            "name": "Pola bahasa sensasional",
            "status": "warning" if language["match_count"] < 3 else "bad",
            "description": f"Ditemukan {language['match_count']} pola bahasa yang sering dipakai untuk menyebarkan hoaks ({phrase_list}).",
        })
        risk.append(f"Ditemukan {language['match_count']} pola bahasa sensasional/ajakan menyebarkan")
    else:
        indicators.append({
            "name": "Pola bahasa sensasional",
            "status": "good",
            "description": "Tidak ditemukan pola bahasa yang umum digunakan dalam konten hoaks.",
        })
        positive.append("Tidak ditemukan pola bahasa sensasional yang mencolok")

    # Sensationalism (caps, punctuation, clickbait)
    caps_ratio = sensationalism["capitalization"]["uppercase_ratio"]
    if caps_ratio >= 25:
        indicators.append({
            "name": "Penggunaan huruf kapital",
            "status": "bad" if caps_ratio >= 40 else "warning",
            "description": f"Sekitar {caps_ratio}% kata ditulis dengan huruf kapital berlebihan.",
        })
        risk.append("Penggunaan huruf kapital berlebihan")
    else:
        indicators.append({
            "name": "Penggunaan huruf kapital",
            "status": "good",
            "description": "Penggunaan huruf kapital berada pada tingkat wajar.",
        })

    if sensationalism["punctuation"]["repeated_punctuation_runs"] > 0:
        indicators.append({
            "name": "Tanda baca berlebihan",
            "status": "warning",
            "description": f"Ditemukan {sensationalism['punctuation']['repeated_punctuation_runs']} penggunaan tanda seru/tanya berulang (contoh: '!!!').",
        })
        risk.append("Tanda baca berlebihan (gaya bahasa sensasional)")
    else:
        indicators.append({
            "name": "Tanda baca berlebihan",
            "status": "good",
            "description": "Tidak ditemukan pola tanda baca berlebihan.",
        })

    if sensationalism["clickbait"]["match_count"] > 0:
        indicators.append({
            "name": "Pola judul/kalimat clickbait",
            "status": "warning",
            "description": f"Ditemukan {sensationalism['clickbait']['match_count']} pola kalimat clickbait.",
        })
        risk.append("Terdapat pola kalimat clickbait")
    else:
        indicators.append({
            "name": "Pola judul/kalimat clickbait",
            "status": "good",
            "description": "Tidak ditemukan pola kalimat clickbait yang umum.",
        })
        positive.append("Tidak ditemukan pola clickbait yang mencolok")

    # Structure
    if structure["score"] >= 80:
        indicators.append({
            "name": "Struktur & panjang teks",
            "status": "good",
            "description": f"Teks terdiri dari {structure['word_count']} kata dan {structure['sentence_count']} kalimat dengan struktur yang cukup lengkap.",
        })
        positive.append("Struktur artikel terlihat cukup lengkap")
    else:
        indicators.append({
            "name": "Struktur & panjang teks",
            "status": "warning",
            "description": f"Teks relatif pendek/kurang terstruktur ({structure['word_count']} kata, {structure['sentence_count']} kalimat), sehingga sulit dinilai secara menyeluruh.",
        })
        risk.append("Teks terlalu pendek atau kurang terstruktur untuk dinilai menyeluruh")

    # Fact check
    indicators.append({
        "name": "Bukti pemeriksaan fakta eksternal",
        "status": "neutral",
        "description": fact_check["message"],
    })

    return {"indicators": indicators, "positive_indicators": positive, "risk_indicators": risk}


def _build_recommendation(status: str, risk_indicators: list[str]) -> str:
    if status == "Kemungkinan Hoaks":
        return (
            "Jangan langsung membagikan informasi ini. Bandingkan dengan sumber berita kredibel, "
            "cari liputan yang sama dari beberapa media, dan periksa situs pemeriksa fakta sebelum mempercayainya."
        )
    if status == "Perlu Verifikasi":
        return (
            "Lakukan verifikasi tambahan sebelum membagikan: bandingkan dengan media kredibel lain, "
            "periksa tanggal dan konteks aslinya, serta cari laporan dari lembaga pemeriksa fakta."
        )
    return (
        "Tidak ditemukan indikator risiko kuat berdasarkan analisis awal. "
        "Tetap disarankan membandingkan dengan sumber lain untuk informasi yang sangat penting."
    )


def _effective_weights(source_applicable: bool, fact_check_applicable: bool) -> dict:
    """Redistribute weight away from components that have no real evidence.

    Source reputation only carries signal when the input came from a URL
    with a resolvable domain. Fact-check evidence only carries signal when
    an external lookup actually ran (FACT_CHECK_API_ENABLED and it
    returned a result). When either is unavailable, its weight is
    proportionally redistributed across the remaining evidence-based
    components instead of injecting a neutral placeholder score that
    would otherwise dilute genuine risk signals from language/style/
    structure analysis.
    """
    available = {
        "source": source_applicable,
        "language": True,
        "sensationalism": True,
        "structure": True,
        "fact_check": fact_check_applicable,
    }
    total = sum(WEIGHTS[k] for k, ok in available.items() if ok)
    if total <= 0:
        total = 1.0
    return {k: (WEIGHTS[k] / total if available[k] else 0.0) for k in WEIGHTS}


def analyze_content(text: str, source_info: dict, fact_check_info: dict) -> dict:
    """Run the full local analysis pipeline and produce the final scored result.

    Args:
        text: cleaned article/claim text to analyze.
        source_info: result of services.source_checker.check_domain().
        fact_check_info: result of services.fact_checker.search_fact_checks().

    Returns a dict matching the documented /api/analyze response shape.
    """
    language = detect_sensational_language(text)
    sensationalism = analyze_sensationalism(text)
    structure = analyze_structure(text)

    source_applicable = bool(source_info.get("domain"))
    fact_check_applicable = bool(fact_check_info.get("checked"))
    weights = _effective_weights(source_applicable, fact_check_applicable)

    weighted = (
        source_info["score"] * weights["source"]
        + language["score"] * weights["language"]
        + sensationalism["score"] * weights["sensationalism"]
        + structure["score"] * weights["structure"]
        + fact_check_info["score"] * weights["fact_check"]
    )
    final_score = int(round(max(0, min(weighted, 100))))
    status = _status_from_score(final_score)

    built = _build_indicators(language, sensationalism, structure, source_info, fact_check_info)

    if status == "Valid":
        summary = "Tidak ditemukan indikator risiko kuat berdasarkan analisis awal."
    elif status == "Perlu Verifikasi":
        summary = "Ditemukan beberapa indikator yang perlu diverifikasi lebih lanjut sebelum informasi ini dipercaya sepenuhnya."
    else:
        summary = "Ditemukan beberapa indikator risiko kuat yang umum terdapat pada konten hoaks."

    return {
        "score": final_score,
        "status": status,
        "summary": summary,
        "indicators": built["indicators"],
        "positive_indicators": built["positive_indicators"],
        "risk_indicators": built["risk_indicators"],
        "recommendation": _build_recommendation(status, built["risk_indicators"]),
        "score_breakdown": {
            "source_reputation": {
                "value": source_info["score"], "weight": WEIGHTS["source"],
                "applied_weight": weights["source"], "applicable": source_applicable,
            },
            "language_pattern": {
                "value": language["score"], "weight": WEIGHTS["language"],
                "applied_weight": weights["language"], "applicable": True,
            },
            "sensationalism": {
                "value": sensationalism["score"], "weight": WEIGHTS["sensationalism"],
                "applied_weight": weights["sensationalism"], "applicable": True,
            },
            "text_structure": {
                "value": structure["score"], "weight": WEIGHTS["structure"],
                "applied_weight": weights["structure"], "applicable": True,
            },
            "fact_check_evidence": {
                "value": fact_check_info["score"], "weight": WEIGHTS["fact_check"],
                "applied_weight": weights["fact_check"], "applicable": fact_check_applicable,
            },
        },
        "structure": structure,
    }
