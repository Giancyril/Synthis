"""
Tests for src/output/citation_formatter.py

Covers:
- All three styles (APA, MLA, Chicago)
- Complete source (with published_date)
- Source with no date  → n.d. fallback
- Source with partial date (year only, year-month)
- Empty sources list
- Invalid style raises ValueError
"""

import pytest
from src.models.schemas import Source
from src.output.citation_formatter import (
    format_apa,
    format_mla,
    format_chicago,
    format_bibliography,
    _hostname,
    _safe_date,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_source():
    return Source(
        id="S1",
        url="https://www.nature.com/articles/solid-state-batteries",
        title="Solid-State Batteries: Challenges and Prospects",
        snippet="Recent advances in solid-state electrolytes...",
        published_date="2023-09-15",
        credibility_tier="primary",
    )


@pytest.fixture
def no_date_source():
    return Source(
        id="S2",
        url="https://example.com/research",
        title="Research on AI Applications",
        snippet="An overview of AI.",
        published_date=None,
        credibility_tier="secondary",
    )


@pytest.fixture
def year_only_source():
    return Source(
        id="S3",
        url="https://arxiv.org/abs/2312.12345",
        title="Advances in Large Language Models",
        snippet="LLM research summary.",
        published_date="2023",
        credibility_tier="primary",
    )


@pytest.fixture
def year_month_source():
    return Source(
        id="S4",
        url="https://techcrunch.com/2024/04/news",
        title="AI Startup Raises Series B",
        snippet="A startup raised funding.",
        published_date="2024-04",
        credibility_tier="secondary",
    )


# ---------------------------------------------------------------------------
# _hostname helper
# ---------------------------------------------------------------------------

def test_hostname_strips_www():
    assert _hostname("https://www.nature.com/articles/123") == "nature.com"


def test_hostname_no_www():
    assert _hostname("https://arxiv.org/abs/1234") == "arxiv.org"


def test_hostname_no_scheme():
    assert _hostname("nature.com/article") == "nature.com"


# ---------------------------------------------------------------------------
# _safe_date helper
# ---------------------------------------------------------------------------

def test_safe_date_full_iso_apa():
    assert _safe_date("2023-09-15", "apa") == "2023"


def test_safe_date_none_apa():
    assert _safe_date(None, "apa") == "n.d."


def test_safe_date_none_mla():
    assert _safe_date(None, "mla") == "n.d."


def test_safe_date_full_iso_mla():
    result = _safe_date("2023-09-15", "mla")
    # Should contain the year and some month abbreviation
    assert "2023" in result
    assert "Sep" in result or "15" in result


def test_safe_date_year_only_mla():
    assert _safe_date("2023", "mla") == "2023"


def test_safe_date_year_month_mla():
    result = _safe_date("2024-04", "mla")
    assert "2024" in result


# ---------------------------------------------------------------------------
# APA format
# ---------------------------------------------------------------------------

def test_apa_contains_site_name(full_source):
    result = format_apa(full_source)
    assert "nature.com" in result.lower()


def test_apa_contains_year(full_source):
    result = format_apa(full_source)
    assert "2023" in result


def test_apa_contains_title(full_source):
    result = format_apa(full_source)
    assert "Solid-State Batteries" in result


def test_apa_contains_url(full_source):
    result = format_apa(full_source)
    assert full_source.url in result


def test_apa_no_date_uses_nd(no_date_source):
    result = format_apa(no_date_source)
    assert "n.d." in result


def test_apa_format_structure(full_source):
    """APA: Site. (year). Title. URL"""
    result = format_apa(full_source)
    assert "(" in result and ")" in result  # year in parens


# ---------------------------------------------------------------------------
# MLA format
# ---------------------------------------------------------------------------

def test_mla_contains_quoted_title(full_source):
    result = format_mla(full_source)
    assert '"' in result
    assert "Solid-State Batteries" in result


def test_mla_contains_site(full_source):
    result = format_mla(full_source)
    assert "nature.com" in result.lower() or "Nature" in result


def test_mla_contains_date(full_source):
    result = format_mla(full_source)
    assert "2023" in result


def test_mla_no_date_uses_nd(no_date_source):
    result = format_mla(no_date_source)
    assert "n.d." in result


def test_mla_ends_with_period(full_source):
    result = format_mla(full_source)
    assert result.rstrip().endswith(".")


def test_mla_strips_https(full_source):
    result = format_mla(full_source)
    assert "https://" not in result


# ---------------------------------------------------------------------------
# Chicago format
# ---------------------------------------------------------------------------

def test_chicago_contains_site(full_source):
    result = format_chicago(full_source)
    assert "nature.com" in result.lower() or "Nature" in result


def test_chicago_contains_year(full_source):
    result = format_chicago(full_source)
    assert "2023" in result


def test_chicago_contains_quoted_title(full_source):
    result = format_chicago(full_source)
    assert '"' in result
    assert "Solid-State Batteries" in result


def test_chicago_contains_url(full_source):
    result = format_chicago(full_source)
    assert full_source.url in result


def test_chicago_no_date_uses_nd(no_date_source):
    result = format_chicago(no_date_source)
    assert "n.d." in result


# ---------------------------------------------------------------------------
# format_bibliography
# ---------------------------------------------------------------------------

def test_bibliography_apa_header(full_source):
    result = format_bibliography([full_source], "apa")
    assert result.startswith("References")


def test_bibliography_mla_header(full_source):
    result = format_bibliography([full_source], "mla")
    assert result.startswith("Works Cited")


def test_bibliography_chicago_header(full_source):
    result = format_bibliography([full_source], "chicago")
    assert result.startswith("Bibliography")


def test_bibliography_multiple_sources(full_source, no_date_source):
    result = format_bibliography([full_source, no_date_source], "apa")
    # Both sources should appear
    assert "Solid-State Batteries" in result
    assert "Research on AI" in result


def test_bibliography_empty_sources():
    result = format_bibliography([], "apa")
    assert "References" in result
    assert "No sources" in result


def test_bibliography_invalid_style(full_source):
    with pytest.raises(ValueError, match="Unsupported bibliography style"):
        format_bibliography([full_source], "harvard")  # type: ignore


def test_bibliography_alphabetical_order(full_source, no_date_source):
    """Entries should be sorted alphabetically."""
    result = format_bibliography([full_source, no_date_source], "apa")
    lines = [l for l in result.split("\n\n") if l.strip()][1:]  # skip header
    assert lines == sorted(lines, key=str.lower)
