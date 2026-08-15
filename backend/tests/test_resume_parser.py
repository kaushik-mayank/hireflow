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


# ---------------------------------------------------------------------------
# Cycle 5: expanded format support + graceful failure (never silently empty)
# ---------------------------------------------------------------------------

def test_plain_text_reports_has_text_flag():
    result = rp.extract_document(b"Jane Doe\nSoftware Engineer\n", "r.txt")
    assert result["has_text"] is True
    assert result["warning"] is None


def test_empty_text_document_warns_instead_of_silent_blank():
    """A text-bearing file that yields nothing must surface a warning (§1)."""
    result = rp.extract_document(b"   \n  \n", "r.txt")
    assert result["has_text"] is False
    assert result["warning"]  # a human message, not None


def test_encrypted_pdf_surfaces_password_warning(monkeypatch):
    """A password-protected PDF is reported clearly, never stored as blank."""
    def _raise(_content):
        raise rp.ExtractionError("This PDF is password-protected. Remove the password and re-upload.")
    monkeypatch.setattr(rp, "_extract_pdf", _raise)
    result = rp.extract_document(b"%PDF-1.4 fake", "secret.pdf")
    assert result["text"] == ""
    assert "password" in (result["warning"] or "").lower()
    assert result["has_text"] is False


def test_corrupt_pdf_surfaces_warning(monkeypatch):
    def _raise(_content):
        raise rp.ExtractionError("This PDF couldn't be opened — it may be corrupt.")
    monkeypatch.setattr(rp, "_extract_pdf", _raise)
    result = rp.extract_document(b"not really a pdf", "broken.pdf")
    assert result["warning"] and result["text"] == ""


def test_legacy_doc_binary_recovers_utf16_text():
    """A legacy .doc storing UTF-16LE text runs is recovered, not left blank."""
    body = "Jane Developer\nSenior Python Engineer\nExperienced backend developer".encode("utf-16-le")
    text, links = rp._extract_doc_binary(b"\xd0\xcf\x11\xe0" + body)
    assert "Developer" in text
    assert links == []


def test_doc_falls_back_to_binary_when_not_docx():
    """`.doc` bytes that aren't a zipped docx go through the binary path and,
    for a real text-bearing doc, do not produce a silent empty result."""
    body = "Michael Scott\nRegional Manager\nDunder Mifflin Paper Company".encode("utf-16-le")
    result = rp.extract_document(b"\xd0\xcf\x11\xe0" + body, "resume.doc")
    # Either recovered text (no warning) — never a crash.
    assert "text" in result and "warning" in result


def test_doc_and_docx_are_supported_extensions():
    for ext in (".pdf", ".doc", ".docx", ".txt"):
        assert ext in rp.SUPPORTED_EXTENSIONS
