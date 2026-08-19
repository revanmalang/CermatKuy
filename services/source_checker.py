"""Checks a domain's reputation against a local list of known/trusted sources.

This is intentionally a *reputation hint*, not a verdict. A domain that is
not in the trusted list is only "belum teridentifikasi" (not yet
identified) -- it is never treated as evidence of a hoax.
"""

from __future__ import annotations

import json
import os

_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "trusted_sources.json",
)

_TRUSTED_CACHE: set[str] | None = None


def _load_trusted_sources() -> set[str]:
    global _TRUSTED_CACHE
    if _TRUSTED_CACHE is not None:
        return _TRUSTED_CACHE
    try:
        with open(_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _TRUSTED_CACHE = {d.lower().strip() for d in data.get("trusted", [])}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        _TRUSTED_CACHE = set()
    return _TRUSTED_CACHE


def check_domain(domain: str) -> dict:
    """Return a reputation summary for the given domain.

    Score is on a 0-100 scale used as the "Source Reputation" scoring
    component. Unknown domains get a neutral score -- being unlisted is
    not treated as a negative signal.
    """
    domain = (domain or "").lower().strip()
    if not domain:
        return {
            "domain": "",
            "category": "Tidak ada domain",
            "trusted": False,
            "score": 50,
            "description": "Tidak ada informasi domain untuk diperiksa (input berupa teks langsung).",
        }

    trusted_sources = _load_trusted_sources()
    if domain in trusted_sources:
        return {
            "domain": domain,
            "category": "Sumber dikenal",
            "trusted": True,
            "score": 95,
            "description": f"Domain '{domain}' termasuk dalam daftar sumber berita yang dikenal.",
        }

    return {
        "domain": domain,
        "category": "Sumber belum teridentifikasi",
        "trusted": False,
        "score": 55,
        "description": (
            f"Domain '{domain}' belum ada dalam daftar sumber yang dikenal sistem. "
            "Ini bukan berarti sumber tersebut tidak kredibel, hanya belum teridentifikasi."
        ),
    }


def list_trusted_domains() -> list[str]:
    return sorted(_load_trusted_sources())
