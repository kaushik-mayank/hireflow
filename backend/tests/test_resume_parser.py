"""Tests for resume link/email/phone extraction.

Focus is the reported bug: an email mangled by PDF text extraction must still be
recovered exactly from the embedded mailto: annotation, and embedded links must
be classified. These exercise the pure helpers with no file I/O.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import resume_parser as rp  # noqa: E402


def test_mailto_annotation_beats_mangled_text():
    """The exact bug: text says 'pedksmayank03@…' but the mailto link is correct."""
    text = "Skype pedksmayank03@gmail.com"  # glued/mangled visible text
    links = ["mailto:dksmayank03@gmail.com"]
    assert rp._best_email(text, links) == "dksmayank03@gmail.com"


def test_email_falls_back_to_text_when_no_annotation():
    assert rp._best_email("reach me at jane.doe@example.org", []) == "jane.doe@example.org"


def test_email_is_lowercased():
    assert rp._best_email("", ["mailto:Jane.DOE@Example.COM"]) == "jane.doe@example.com"


def test_no_email_returns_none():
    assert rp._best_email("no address here", []) is None


def test_links_are_classified_by_platform():
    links = [
        "https://www.linkedin.com/in/mayank",
        "https://github.com/mayank",
        "https://mayank.dev",
        "mailto:x@y.com",
    ]
    out = rp._classify_links(links)
    assert out["linkedin"] == "https://www.linkedin.com/in/mayank"
    assert out["github"] == "https://github.com/mayank"
    assert out["portfolio"] == "https://mayank.dev"
    # mailto/tel are never treated as browsable links
    assert all(not l.lower().startswith("mailto:") for l in out["links"])


def test_links_are_deduped_and_order_preserved():
    out = rp._classify_links(["https://a.com", "https://a.com", "https://b.com"])
    assert out["links"] == ["https://a.com", "https://b.com"]


def test_first_non_social_link_becomes_portfolio():
    out = rp._classify_links(["https://myfolio.example", "https://github.com/x"])
    assert out["portfolio"] == "https://myfolio.example"
    assert out["github"] == "https://github.com/x"


def test_unsupported_extension_yields_empty_document():
    result = rp.extract_document(b"whatever", "resume.rtf")
    assert result["text"] == ""
    assert result["email"] is None
    assert result["links"] == []


def test_plain_text_document_extracts_email_and_url():
    content = b"Mayank\nEmail: mayank@example.com\nSite: https://mayank.dev\n"
    result = rp.extract_document(content, "resume.txt")
    assert result["email"] == "mayank@example.com"
    assert result["portfolio"] == "https://mayank.dev"


def test_ocr_absence_is_not_fatal():
    """An image upload with no OCR available returns empty text, not an error."""
    result = rp.extract_document(b"\x89PNG\r\n", "scan.png")
    assert result["text"] == ""
    assert "links" in result
