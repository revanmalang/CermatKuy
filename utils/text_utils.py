"""Reusable text-processing and URL-safety helpers.

These functions intentionally avoid any heavy NLP dependency. Everything
here is plain string/regex processing, which keeps CermatKuy runnable
with no model downloads and no external services.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Basic text limits (also enforced again in app.py request validation)
# ---------------------------------------------------------------------------
MIN_TEXT_LENGTH = 20
MAX_TEXT_LENGTH = 20000

# Sentence splitting on ., !, ?, and Indonesian-friendly line breaks.
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9']+")
_REPEATED_PUNCT_RE = re.compile(r"([!?]){2,}")
_WHITESPACE_RE = re.compile(r"\s+")

# Hostnames that must never be reachable from the URL fetcher (SSRF guard).
_BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
}


def clean_whitespace(text: str) -> str:
    """Collapse repeated whitespace/newlines into single spaces and trim."""
    return _WHITESPACE_RE.sub(" ", text or "").strip()


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text) if p.strip()]
    return parts


def count_sentences(text: str) -> int:
    return len(split_sentences(text))


def count_paragraphs(text: str) -> int:
    if not text:
        return 0
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    # Fall back to 1 paragraph if the text has no blank-line breaks at all.
    return len(paragraphs) if paragraphs else (1 if text.strip() else 0)


def uppercase_word_ratio(text: str) -> float:
    """Percentage of alphabetic words that are entirely uppercase (len >= 3)."""
    words = [w for w in _WORD_RE.findall(text or "") if any(c.isalpha() for c in w)]
    eligible = [w for w in words if len(w) >= 3]
    if not eligible:
        return 0.0
    shouting = [w for w in eligible if w.isupper()]
    return round(len(shouting) / len(eligible) * 100, 1)


def count_exclamations(text: str) -> int:
    return (text or "").count("!")


def count_questions(text: str) -> int:
    return (text or "").count("?")


def count_repeated_punctuation(text: str) -> int:
    """Number of runs of 2+ consecutive '!' or '?' characters (e.g. '!!!', '??')."""
    return len(_REPEATED_PUNCT_RE.findall(text or ""))


def truncate(text: str, max_length: int) -> str:
    if text and len(text) > max_length:
        return text[:max_length]
    return text or ""


# ---------------------------------------------------------------------------
# URL validation / SSRF protection
# ---------------------------------------------------------------------------

def is_valid_http_url(url: str) -> bool:
    """True if url is syntactically a well-formed http(s) URL."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    return True


def _is_private_or_reserved(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable -> treat as unsafe
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def is_safe_public_url(url: str) -> tuple[bool, str]:
    """Best-effort SSRF guard: reject localhost, private, and reserved targets.

    Returns (is_safe, reason_if_unsafe).
    """
    if not is_valid_http_url(url):
        return False, "URL tidak valid."

    hostname = (urlparse(url.strip()).hostname or "").lower()
    if not hostname:
        return False, "URL tidak memiliki host yang valid."
    if hostname in _BLOCKED_HOSTNAMES:
        return False, "Akses ke alamat lokal tidak diizinkan."

    # If the hostname is itself a literal IP, check it directly.
    try:
        ipaddress.ip_address(hostname)
        if _is_private_or_reserved(hostname):
            return False, "Akses ke alamat IP privat/lokal tidak diizinkan."
        return True, ""
    except ValueError:
        pass  # not a literal IP, fall through to DNS resolution

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False, "Domain tidak dapat ditemukan (DNS resolution gagal)."

    resolved_ips = {info[4][0] for info in infos}
    if not resolved_ips:
        return False, "Domain tidak dapat di-resolve."

    for ip_str in resolved_ips:
        if _is_private_or_reserved(ip_str):
            return False, "Domain mengarah ke alamat jaringan privat/lokal."

    return True, ""


def get_domain(url: str) -> str:
    """Extract a normalized domain (no 'www.', lowercase) from a URL."""
    try:
        netloc = urlparse(url.strip()).netloc.lower()
    except (ValueError, AttributeError):
        return ""
    netloc = netloc.split("@")[-1]  # strip userinfo if present
    netloc = netloc.split(":")[0]   # strip port
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc
