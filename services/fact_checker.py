"""External fact-check API abstraction.

CermatKuy ships with no external fact-check API configured, so this
module always returns an "not enabled" result and the app relies on the
local heuristic analyzer instead. The function signatures here are the
integration point for a future real integration (e.g. Google Fact Check
Tools API, TurnBackHoax, atau layanan cek fakta lainnya) -- no fabricated results are
ever produced.

To enable a real integration later:
    1. Set FACT_CHECK_API_ENABLED = True below.
    2. Implement `_query_external_api()` to call the real API and return
       genuine claim-review results in the same shape as the "claims"
       list documented in `search_fact_checks()`.
    3. Provide any required API key via an environment variable and read
       it inside `_query_external_api()`.
"""

from __future__ import annotations

# Master switch. Kept False until a real API integration is wired in.
FACT_CHECK_API_ENABLED = False

NOT_ENABLED_MESSAGE = "Pencarian database fact-check eksternal belum diaktifkan."


def _query_external_api(query: str) -> list[dict]:
    """Placeholder for a real external fact-check API call.

    Not implemented -- intentionally left as a stub so the app never
    fabricates fact-check results. When FACT_CHECK_API_ENABLED is True,
    implement the real HTTP call here and return a list of claim-review
    dicts shaped like: {"claim": str, "rating": str, "publisher": str, "url": str}.
    """
    raise NotImplementedError("External fact-check API integration is not configured.")


def search_fact_checks(query: str) -> dict:
    """Look up `query` against configured fact-check sources.

    Returns:
        {
            "enabled": bool,
            "checked": bool,       # whether an external lookup actually ran
            "claims": list[dict],  # empty unless a real API is enabled and returns matches
            "score": int,          # 0-100 "Fact Check Evidence" scoring component
            "message": str,        # human-readable status
        }

    When disabled (the default), this returns a neutral score and a clear
    message rather than pretending evidence was searched.
    """
    if not FACT_CHECK_API_ENABLED:
        return {
            "enabled": False,
            "checked": False,
            "claims": [],
            "score": 50,
            "message": NOT_ENABLED_MESSAGE,
        }

    try:
        claims = _query_external_api(query)
    except NotImplementedError:
        return {
            "enabled": True,
            "checked": False,
            "claims": [],
            "score": 50,
            "message": "API fact-check aktif tetapi belum terhubung dengan benar.",
        }

    if not claims:
        return {
            "enabled": True,
            "checked": True,
            "claims": [],
            "score": 55,
            "message": "Tidak ditemukan hasil pemeriksaan fakta terkait dari database eksternal.",
        }

    return {
        "enabled": True,
        "checked": True,
        "claims": claims,
        "score": 50,
        "message": f"Ditemukan {len(claims)} hasil terkait dari database fact-check eksternal.",
    }
