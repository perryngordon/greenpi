"""
Markdown rendering shared by the wiki, blog and almanac.

* [[Page Name]] / [[Page Name|link text]] become links to wiki pages.
* Output is sanitised with nh3, so stored text can never inject scripts.
"""
import re

import markdown
import nh3
from django.utils.text import slugify

WIKI_LINK = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]")

ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3",
    "h4", "h5", "h6", "hr", "i", "img", "li", "ol", "p", "pre", "s", "strong",
    "sub", "sup", "table", "tbody", "td", "th", "thead", "tr", "ul",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "class"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "th": {"align"},
    "td": {"align"},
}


def wiki_slug(title):
    return slugify(title.strip())[:120] or "page"


def wiki_links(text):
    """Return the slugs of every [[wiki link]] in the text."""
    return {wiki_slug(m.group(1)) for m in WIKI_LINK.finditer(text or "")}


def _replace_wiki_link(m):
    title = m.group(1).strip()
    label = (m.group(2) or title).strip()
    return f'<a class="wikilink" href="#/wiki/{wiki_slug(title)}">{label}</a>'


def render(text):
    """Markdown (with [[wiki links]]) -> sanitised HTML."""
    html = markdown.markdown(
        WIKI_LINK.sub(_replace_wiki_link, text or ""),
        extensions=["extra", "sane_lists", "nl2br"],
    )
    html = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
    )
    # Lazy-load images (photos can be large on a slow link).
    return html.replace("<img ", '<img loading="lazy" ')


def excerpt(text, length=220):
    """Plain-text start of a Markdown body for list views."""
    plain = nh3.clean(markdown.markdown(WIKI_LINK.sub(lambda m: (m.group(2) or m.group(1)), text or "")), tags=set())
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain if len(plain) <= length else plain[: length - 1].rsplit(" ", 1)[0] + "…"
