"""Builds the digest email: minimal HTML (inline styles, since email apps
ignore <style> blocks) plus a plain-text version."""

from dataclasses import dataclass
from datetime import date
from html import escape

SECTION_TITLES = {
    "tech": "Tech",
    "business": "Business",
    "politics": "Politics",
    "education": "Education & Visas (F-1, OPT, H-1B)",
}


@dataclass
class EmailStory:
    title: str
    url: str
    outlet: str
    summary: str
    about_india: bool


def build_subject(digest_date: date) -> str:
    return f"Your daily news digest — {digest_date:%a, %d %b %Y}"


def build_html(
    digest_date: date, greeting: str, intro: str, sections: dict[str, list[EmailStory]]
) -> str:
    parts = [
        '<div style="max-width:640px;margin:0 auto;font-family:Arial,Helvetica,sans-serif;'
        'color:#1f2328;line-height:1.5;">',
        f'<p style="font-size:13px;color:#6e7781;margin:0 0 4px;">{digest_date:%A, %d %B %Y}</p>',
        f'<h1 style="font-size:22px;margin:0 0 8px;">{escape(greeting)}</h1>',
        f'<p style="font-size:15px;margin:0 0 20px;">{escape(intro)}</p>',
    ]
    for section, stories in sections.items():
        if not stories:
            continue
        parts.append(
            f'<h2 style="font-size:17px;margin:28px 0 8px;padding-bottom:4px;'
            f'border-bottom:2px solid #d0d7de;">{SECTION_TITLES.get(section, section.title())}</h2>'
        )
        for i, s in enumerate(stories, start=1):
            badge = (
                ' <span style="font-size:11px;background:#fff1e5;color:#9a4b00;'
                'border-radius:4px;padding:1px 6px;">🇮🇳 India</span>'
                if s.about_india
                else ""
            )
            parts.append(
                '<div style="margin:0 0 16px;">'
                f'<p style="margin:0;font-size:15px;"><b>{i}. '
                f'<a href="{escape(s.url, quote=True)}" style="color:#0969da;text-decoration:none;">'
                f"{escape(s.title)}</a></b>{badge}</p>"
                f'<p style="margin:2px 0 4px;font-size:12px;color:#6e7781;"><i>{escape(s.outlet)}</i></p>'
                f'<p style="margin:0;font-size:14px;">{escape(s.summary)}</p>'
                "</div>"
            )
    parts.append(
        '<p style="font-size:12px;color:#6e7781;margin:32px 0 0;border-top:1px solid #d0d7de;'
        'padding-top:8px;">Summaries are written by AI from each outlet\'s headline and description '
        "— open the link for the full story.</p></div>"
    )
    return "".join(parts)


def build_text(
    digest_date: date, greeting: str, intro: str, sections: dict[str, list[EmailStory]]
) -> str:
    lines = [f"{digest_date:%A, %d %B %Y}", "", greeting, intro, ""]
    for section, stories in sections.items():
        if not stories:
            continue
        lines += [SECTION_TITLES.get(section, section.title()).upper(), ""]
        for i, s in enumerate(stories, start=1):
            india = " [India]" if s.about_india else ""
            lines += [f"{i}. {s.title}{india} ({s.outlet})", f"   {s.summary}", f"   {s.url}", ""]
    return "\n".join(lines)
