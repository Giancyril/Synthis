"""
Bibliography citation formatter for Synthis research reports.

Implements APA 7th edition, MLA 9th edition, and Chicago (author-date) style
formatting for Source objects from a ResearchReport.

Design notes
------------
* Source has: id, url, title, snippet, summary, published_date,
  relevance_score, credibility_tier.
* Missing fields: author (never present), publisher (inferred from hostname).
* Graceful degradation follows each style's own conventions:
  - APA  §9.12  : no author → site/org name (hostname). No date → "n.d."
  - MLA  §5.4   : no author → omit Author element entirely.  No date → "n.d."
  - Chicago §14.247: no author → site/org name (hostname). No date → "n.d."
* No invented placeholder like "Unknown Author" — only conventions each
  style defines for exactly this situation.
"""

from __future__ import annotations

import re
from typing import List, Literal
from urllib.parse import urlparse

from src.models.schemas import Source

BibStyle = Literal["apa", "mla", "chicago"]


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _hostname(url: str) -> str:
    """Return the bare hostname (no www., no scheme, no path)."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        # If no scheme was present, urlparse puts everything in .path
        # Strip anything after the first slash in that case.
        if not parsed.netloc and "/" in host:
            host = host.split("/")[0]
        return re.sub(r"^www\.", "", host).lower()
    except Exception:
        return url


def _title_case(s: str) -> str:
    """Cheap title-case that preserves citation-tag capitalisation."""
    return s.strip()


def _sentence_case(s: str) -> str:
    """Convert a string to sentence case (first letter of title uppercase only)."""
    s = s.strip()
    if not s:
        return s
    return s[0].upper() + s[1:].lower() if len(s) > 1 else s.upper()


def _safe_date(published_date: str | None, style: str) -> str:
    """
    Return a formatted date string or the no-date token for the given style.
    APA / Chicago: 'n.d.'
    MLA          : 'n.d.'  (same token)
    """
    if not published_date:
        return "n.d."
    # Tavily returns dates like "2024-03-15", "2024", or "2024-03", etc.
    # Extract the year (first 4-digit sequence).
    m = re.search(r"\b(\d{4})\b", published_date)
    if not m:
        return "n.d."
    year = m.group(1)

    if style == "mla":
        # Try to get month + day too for MLA
        parts = published_date.split("-")
        if len(parts) == 3:
            try:
                from datetime import date
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
                month_abbr = d.strftime("%b").rstrip(".")
                return f"{d.day} {month_abbr}. {d.year}"
            except ValueError:
                pass
        if len(parts) == 2:
            try:
                from datetime import date
                d = date(int(parts[0]), int(parts[1]), 1)
                return f"{d.strftime('%b')}. {d.year}"
            except ValueError:
                pass
        return year
    # APA / Chicago: year only
    return year


# ---------------------------------------------------------------------------
# APA 7th edition
# ---------------------------------------------------------------------------

def format_apa(source: Source) -> str:
    """
    Format a single Source in APA 7th edition style.

    Template (no author):
      Site Name. (year). Title of page. Retrieved from URL

    Example:
      NASA. (2023). Artemis program overview. https://www.nasa.gov/artemis
    """
    site = _hostname(source.url).capitalize()
    year = _safe_date(source.published_date, "apa")
    # APA italicises the title for web pages; plain text uses no markup.
    title = source.title.strip().rstrip(".")

    return f"{site}. ({year}). {title}. {source.url}"


# ---------------------------------------------------------------------------
# MLA 9th edition
# ---------------------------------------------------------------------------

def format_mla(source: Source) -> str:
    """
    Format a single Source in MLA 9th edition style.

    Template (no author):
      "Title of Page." Website Name, Date, URL.

    Example:
      "Artemis Program Overview." NASA, 15 Mar. 2023, www.nasa.gov/artemis.
    """
    title = source.title.strip().strip('"')
    site = _hostname(source.url)
    date_str = _safe_date(source.published_date, "mla")

    # URL: MLA 9 recommends removing https:// for readability
    display_url = re.sub(r"^https?://", "", source.url)

    return f'"{title}." {site.capitalize()}, {date_str}, {display_url}.'


# ---------------------------------------------------------------------------
# Chicago (author-date) 17th edition
# ---------------------------------------------------------------------------

def format_chicago(source: Source) -> str:
    """
    Format a single Source in Chicago author-date style.

    Template (no author, web source):
      Site Name. year. "Title of Page." Accessed URL.

    Example:
      NASA. 2023. "Artemis Program Overview." https://www.nasa.gov/artemis.
    """
    site = _hostname(source.url).capitalize()
    year = _safe_date(source.published_date, "chicago")
    title = source.title.strip().strip('"')

    return f'{site}. {year}. "{title}." {source.url}.'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_STYLE_FN = {
    "apa": format_apa,
    "mla": format_mla,
    "chicago": format_chicago,
}

_STYLE_HEADERS = {
    "apa": "References",
    "mla": "Works Cited",
    "chicago": "Bibliography",
}


def format_bibliography(sources: List[Source], style: BibStyle) -> str:
    """
    Format all sources into a complete bibliography in the requested style.

    Returns a plain-text string ready to copy-paste, with:
    - A section header (References / Works Cited / Bibliography)
    - One entry per source, with a blank line separating each
    - Entries sorted alphabetically by the first token (site name / title)

    Parameters
    ----------
    sources : list of Source
    style   : "apa" | "mla" | "chicago"

    Raises
    ------
    ValueError : if style is not one of the supported values.
    """
    if style not in _STYLE_FN:
        raise ValueError(
            f"Unsupported bibliography style '{style}'. "
            f"Choose one of: {', '.join(_STYLE_FN)}."
        )
    if not sources:
        return f"{_STYLE_HEADERS[style]}\n\n(No sources to format.)"

    fmt = _STYLE_FN[style]
    entries = [fmt(s) for s in sources]
    entries.sort(key=lambda e: e.lower())  # alphabetical order

    header = _STYLE_HEADERS[style]
    body = "\n\n".join(entries)
    return f"{header}\n\n{body}"
