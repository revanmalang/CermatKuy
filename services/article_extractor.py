"""Fetches a news article URL and extracts clean, readable text from it."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

from utils.text_utils import clean_whitespace, get_domain, is_safe_public_url

_REQUEST_TIMEOUT = 8  # seconds
_MAX_DOWNLOAD_BYTES = 3_000_000  # 3 MB safety cap
_USER_AGENT = (
    "Mozilla/5.0 (compatible; CermatKuy/1.0; "
    "+https://github.com/cermatkuy) local-fact-check-bot"
)

# Tags whose content is never part of the readable article body.
_TAGS_TO_STRIP = [
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "iframe",
    "noscript",
    "svg",
    "button",
]


class ArticleExtractionError(Exception):
    """Raised when an article cannot be safely fetched or meaningfully parsed."""


def extract_article(url: str) -> dict:
    """Fetch `url` and return {title, domain, content, meta_description, url}.

    Raises ArticleExtractionError with a user-friendly message on any
    failure (invalid URL, SSRF-blocked target, network error, non-HTML
    response, or an article with no extractable text).
    """
    is_safe, reason = is_safe_public_url(url)
    if not is_safe:
        raise ArticleExtractionError(
            "URL tidak dapat diproses: " + (reason or "URL tidak valid.")
        )

    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=_REQUEST_TIMEOUT,
            allow_redirects=True,
            stream=True,
        )
    except requests.exceptions.Timeout:
        raise ArticleExtractionError(
            "Artikel tidak dapat diakses (waktu tunggu habis). Silakan tempel isi berita secara langsung."
        )
    except requests.exceptions.SSLError:
        raise ArticleExtractionError(
            "Artikel tidak dapat diakses (masalah sertifikat SSL). Silakan tempel isi berita secara langsung."
        )
    except requests.exceptions.ConnectionError:
        raise ArticleExtractionError(
            "Artikel tidak dapat diakses (gagal terhubung). Silakan tempel isi berita secara langsung."
        )
    except requests.exceptions.RequestException:
        raise ArticleExtractionError(
            "Artikel tidak dapat diakses. Silakan tempel isi berita secara langsung."
        )

    # Re-check the final URL (after redirects) against the SSRF guard, since
    # a server could redirect to an internal address.
    final_url = response.url
    is_safe_final, reason_final = is_safe_public_url(final_url)
    if not is_safe_final:
        response.close()
        raise ArticleExtractionError(
            "URL dialihkan ke alamat yang tidak diizinkan: " + (reason_final or "")
        )

    if response.status_code != 200:
        response.close()
        raise ArticleExtractionError(
            f"Artikel tidak dapat diakses (HTTP {response.status_code}). "
            "Silakan tempel isi berita secara langsung."
        )

    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        response.close()
        raise ArticleExtractionError(
            "URL tidak mengarah ke halaman HTML/berita. Silakan tempel isi berita secara langsung."
        )

    raw_bytes = bytearray()
    for chunk in response.iter_content(chunk_size=65536):
        raw_bytes.extend(chunk)
        if len(raw_bytes) > _MAX_DOWNLOAD_BYTES:
            response.close()
            raise ArticleExtractionError(
                "Halaman terlalu besar untuk diproses. Silakan tempel isi berita secara langsung."
            )
    response.close()

    try:
        html = raw_bytes.decode(response.encoding or "utf-8", errors="replace")
    except (LookupError, TypeError):
        html = raw_bytes.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html, "html.parser")

    for tag_name in _TAGS_TO_STRIP:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = clean_whitespace(soup.title.string)
    if not title:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = clean_whitespace(og_title["content"])

    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_description = clean_whitespace(meta_tag["content"])
    else:
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            meta_description = clean_whitespace(og_desc["content"])

    # Prefer <article> content when present, otherwise fall back to all <p> tags.
    article_tag = soup.find("article")
    if article_tag:
        paragraphs = [clean_whitespace(p.get_text(" ")) for p in article_tag.find_all("p")]
    else:
        paragraphs = [clean_whitespace(p.get_text(" ")) for p in soup.find_all("p")]

    paragraphs = [p for p in paragraphs if len(p) > 30]
    content = "\n\n".join(paragraphs)

    if not content and meta_description:
        content = meta_description

    if not content or len(content) < 50:
        raise ArticleExtractionError(
            "Artikel tidak dapat diakses. Silakan tempel isi berita secara langsung."
        )

    return {
        "url": final_url,
        "title": title or "(Judul tidak ditemukan)",
        "domain": get_domain(final_url),
        "content": content,
        "meta_description": meta_description,
    }
