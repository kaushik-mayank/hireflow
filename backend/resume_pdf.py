"""Render a candidate's structured resume to a downloadable PDF.

Uses reportlab (already a dependency). The layout mirrors the on-screen
`ResumeView` sections — header, summary, experience, education, skills,
certifications, languages — so the download matches what the user sees.

reportlab is imported lazily inside `build_resume_pdf` so importing this module
never requires it (keeps the offline test suite, which stubs the DB and never
calls this, working without reportlab installed).
"""

from io import BytesIO


def _as_list(v):
    return v if isinstance(v, list) else []


def build_resume_pdf(structured: dict, cand: dict) -> bytes:
    """Return PDF bytes for a candidate's resume. Falls back to the raw resume
    text when no structured data has been generated yet."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem,
    )

    d = structured or {}
    contact = d.get("contact") if isinstance(d.get("contact"), dict) else {}
    links = d.get("links") if isinstance(d.get("links"), dict) else {}

    base = getSampleStyleSheet()
    name_style = ParagraphStyle("Name", parent=base["Title"], fontSize=20, spaceAfter=2, alignment=TA_LEFT, textColor=colors.HexColor("#1f2937"))
    headline_style = ParagraphStyle("Headline", parent=base["Normal"], fontSize=11, textColor=colors.HexColor("#4f6ef7"), spaceAfter=4)
    meta_style = ParagraphStyle("Meta", parent=base["Normal"], fontSize=8.5, textColor=colors.HexColor("#6b7280"), spaceAfter=2)
    section_style = ParagraphStyle("Section", parent=base["Heading2"], fontSize=10.5, textColor=colors.HexColor("#6b7280"), spaceBefore=12, spaceAfter=4)
    role_style = ParagraphStyle("Role", parent=base["Normal"], fontSize=11, spaceAfter=1, textColor=colors.HexColor("#1f2937"))
    dates_style = ParagraphStyle("Dates", parent=base["Normal"], fontSize=8.5, textColor=colors.HexColor("#6b7280"), spaceAfter=2)
    body_style = ParagraphStyle("Body", parent=base["Normal"], fontSize=9.5, leading=13, textColor=colors.HexColor("#374151"))
    bullet_style = ParagraphStyle("Bullet", parent=body_style, leftIndent=6)

    def esc(text):
        return (str(text or "")
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    story = []
    story.append(Paragraph(esc(d.get("name") or cand.get("name") or "Candidate"), name_style))
    if d.get("headline"):
        story.append(Paragraph(esc(d["headline"]), headline_style))

    meta_bits = [contact.get("email") or cand.get("email"), contact.get("phone") or cand.get("phone"),
                 contact.get("location"), links.get("linkedin"), links.get("github"), links.get("portfolio")]
    meta = "  •  ".join(esc(m) for m in meta_bits if m)
    if meta:
        story.append(Paragraph(meta, meta_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#111827"), spaceBefore=4, spaceAfter=2))

    def section(title):
        story.append(Paragraph(title.upper(), section_style))

    if d.get("summary"):
        section("Summary")
        story.append(Paragraph(esc(d["summary"]), body_style))

    experience = _as_list(d.get("experience"))
    if experience:
        section("Experience")
        for e in experience:
            if not isinstance(e, dict):
                continue
            title = esc(e.get("title"))
            org = esc(e.get("organization"))
            head = f"<b>{title}</b>" + (f" · {org}" if org else "")
            story.append(Paragraph(head or "Role", role_style))
            line2 = " · ".join(x for x in [esc(e.get("dates")), esc(e.get("location"))] if x)
            if line2:
                story.append(Paragraph(line2, dates_style))
            highs = [esc(h) for h in _as_list(e.get("highlights")) if h]
            if highs:
                story.append(ListFlowable([ListItem(Paragraph(h, bullet_style), leftIndent=10) for h in highs],
                                          bulletType="bullet", start="•", spaceAfter=4))
            story.append(Spacer(1, 4))

    education = _as_list(d.get("education"))
    if education:
        section("Education")
        for e in education:
            if not isinstance(e, dict):
                continue
            q = esc(e.get("qualification"))
            inst = esc(e.get("institution"))
            dates = esc(e.get("dates"))
            line = f"<b>{q}</b>" + (f" · {inst}" if inst else "") + (f"  ({dates})" if dates else "")
            story.append(Paragraph(line or "—", body_style))

    skills = [esc(s) for s in _as_list(d.get("skills")) if s]
    if skills:
        section("Skills")
        story.append(Paragraph("  ·  ".join(skills), body_style))

    certs = [esc(c) for c in _as_list(d.get("certifications")) if c]
    if certs:
        section("Certifications & Licences")
        story.append(ListFlowable([ListItem(Paragraph(c, bullet_style), leftIndent=10) for c in certs],
                                  bulletType="bullet", start="•"))

    langs = [esc(l) for l in _as_list(d.get("languages")) if l]
    if langs:
        section("Languages")
        story.append(Paragraph("  ·  ".join(langs), body_style))

    # Fallback: if there is no structured content at all, dump the raw text so
    # the download is never empty.
    if len(story) <= 3 and cand.get("resume_text"):
        for para in str(cand["resume_text"]).split("\n"):
            story.append(Paragraph(esc(para) or "&nbsp;", body_style))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch, title="Resume")
    doc.build(story)
    return buf.getvalue()
