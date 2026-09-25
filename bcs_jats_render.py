#!/usr/bin/env python3
"""
bcs_jats_render.py... turn an editor project (see bcs_editor.py) into
a JATS 1.4 Journal Publishing XML file.

"""

import html
import re
from pathlib import Path

from bcs_config import (JOURNAL, COPYRIGHT_HOLDER, LICENSE, COPYRIGHT_AGREEMENT,
                        RIGHTS_DEFAULT, CC_FROM_YEAR, SECTION_MAP, SECTION_DEFAULT)
from bcs_editor import (
    _split_at, analyze_ref, editor_html_to_jats, esc, esc_attr, html_to_tokens,
    title_plain, title_tokens, tokens_plain, tokens_to_jats,
)
from bcs_profiles import (
    ARCHIVAL, DEFAULT_PROFILE, LENS, PROFILES, TOOL_VERSION, get_profile,
)

# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

_TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")
_URL_RE = re.compile(r"https?://[^\s<>\"]+")
_TRAILING_PUNCT = ".,;:)]}”’"


# A "URL" whose host is a DOI prefix (e.g. https://10.14288/x) is a mistyped
# DOI, not a resolvable address -- recover it instead of emitting a dead link.
_DOI_AS_URL_RE = re.compile(r"^https?://(10\.\d{4,9}/\S+)$")


def _linkify_text(text, citation=False):
    """Wrap bare URLs in <ext-link>.

    citation=True is used inside <mixed-citation>: doi.org links get
    ext-link-type="doi" (JATS4R style for references; the Lens viewer never
    reads mixed-citations so its type="doi" href-prefixing quirk is moot).
    In body text (citation=False) doi.org links must stay type="uri":
    Lens prepends "http://dx.doi.org/" to the href of every body ext-link
    whose type is "doi", which would break an already-full URL.
    """
    def repl(m):
        url = m.group(0)
        trailing = ""
        while url and url[-1] in _TRAILING_PUNCT:
            trailing = url[-1] + trailing
            url = url[:-1]
        if not url:
            return m.group(0)
        href = url
        dm = _DOI_AS_URL_RE.match(url)
        if dm:  # display the printed text, but point at the real resolver
            href = "https://doi.org/" + dm.group(1)
        is_doi = "doi.org/" in href
        link_type = "doi" if (is_doi and citation) else "uri"
        return (f'<ext-link ext-link-type="{link_type}" xlink:href="{href}">'
                f"{url}</ext-link>{trailing}")
    return _URL_RE.sub(repl, text)


def linkify_urls(xml_string):
    parts = _TAG_SPLIT_RE.split(xml_string)
    return "".join(p if p.startswith("<") else _linkify_text(p) for p in parts)


def slugify(text, maxlen=50):
    text = re.sub(r"[^\w\s-]", "", (text or "").lower())
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:maxlen] or "untitled"


def _norm_section(name):
    # "fora" is a CanLit leftover; harmless for BC Studies
    low = " ".join((name or "").split()).strip().lower()
    return {"fora": "forum"}.get(low, low)


def section_lookup(section_text):
    return SECTION_MAP.get(_norm_section(section_text), SECTION_DEFAULT)


def _split_paras(html_str):
    """Split a contenteditable's HTML into paragraph strings on <p>/<div>
    boundaries (or double <br>)."""
    s = (html_str or "").strip()
    if not s:
        return []
    s = re.sub(r"</?(?:p|div)[^>]*>", "\x00", s)
    s = re.sub(r"(?:<br\s*/?>\s*){2,}", "\x00", s)
    s = s.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
    paras = [p.strip() for p in s.split("\x00")]
    return [p for p in paras if p]


def _paras_to_jats(html_str, wrap="p"):
    out = []
    for p in _split_paras(html_str):
        inner = linkify_urls(editor_html_to_jats(p))
        out.append(f"<{wrap}>{inner}</{wrap}>")
    return "".join(out)


# ---------------------------------------------------------------------------
# mixed-citation: display-faithful text with structured tags embedded
# ---------------------------------------------------------------------------

def _issue_editors_xml(meta):
    """Masthead editors, in their own contrib-group. The article's own
    contrib-group has no content-type, which is how the XSLT tells the two
    apart."""
    groups = []
    for key, ctype in (("issue_editors", "editor"),):
        names = [n.strip() for n in (meta.get(key) or "").split(" and ") if n.strip()]
        if not names:
            continue
        contribs = []
        for n in names:
            bits = n.split()
            if len(bits) >= 2:
                inner = (f"<surname>{esc(bits[-1])}</surname>"
                         f"<given-names>{esc(' '.join(bits[:-1]))}</given-names>")
            else:
                inner = f"<surname>{esc(n)}</surname>"
            contribs.append(f'<contrib contrib-type="{ctype}"><name>{inner}</name></contrib>')
        groups.append(f'<contrib-group content-type="{ctype}">{"".join(contribs)}</contrib-group>')
    return "".join(groups)


def _orcids(meta, n_people):
    """One ORCID per author, in byline order, from the Metadata tab's
    'ORCID(s)' field ("0000-0002-1825-0097 and 0000-..."). A blank slot
    ("- and 0000-...") skips an author. Returns bare identifiers."""
    raw = (meta.get("orcids") or "").strip()
    if not raw:
        return [""] * n_people
    out = []
    for piece in re.split(r"\s+and\s+|\s*;\s*", raw):
        piece = piece.strip()
        m = re.search(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])", piece, re.I)
        out.append(m.group(1).upper() if m else "")
    out = (out + [""] * n_people)[:n_people]
    return out


def _wrap_names(escaped_prefix, people, group_type):
    """Wrap each printed author name in the (already escaped/serialized)
    author segment with <string-name>/<surname>/<given-names>."""
    s = escaped_prefix

    def _outside_markup(match_start):
        """string-name may not sit inside italic/bold -- only wrap names in
        plain text."""
        before = s[:match_start]
        for tag in ("italic", "bold"):
            if before.count(f"<{tag}>") > before.count(f"</{tag}>"):
                return False
        return True

    for idx, (sur, giv) in enumerate(people):
        sur_e, giv_e = esc(sur), esc(giv)
        if idx == 0 and giv:
            pat = re.escape(sur_e) + r",\s*" + re.escape(giv_e)
            rep = (f"<string-name><surname>{sur_e}</surname>, "
                   f"<given-names>{giv_e}</given-names></string-name>")
        elif giv:
            pat = re.escape(giv_e) + r"\s+" + re.escape(sur_e)
            rep = (f"<string-name><given-names>{giv_e}</given-names> "
                   f"<surname>{sur_e}</surname></string-name>")
        else:
            pat = r"\b" + re.escape(sur_e) + r"\b"
            rep = f"<string-name><surname>{sur_e}</surname></string-name>"
        m = re.search(pat, s)
        if m and _outside_markup(m.start()):
            s = s[:m.start()] + rep + s[m.end():]
    return s


def _micro_wrap_tail(tail_xml, a):
    """Wrap year / vol / no. / pages / DOI / URLs inside the serialized tail
    of a mixed-citation, touching only text between tags."""
    done = {"year": False, "vol": False, "no": False, "pp": False}

    def wrap_text(text):
        # volume BEFORE year: in "vol. 2022, no. 274, 2022" the first 2022 is
        # the volume number -- wrapping year first put <year> in its place
        if a["volume"] and not done["vol"]:
            text, n = re.subn(r"(vol\.\s*)" + re.escape(a["volume"]) + r"\b",
                              rf"\1<volume>{a['volume']}</volume>", text,
                              count=1, flags=re.IGNORECASE)
            if n:
                done["vol"] = True
        if a["year"] and not done["year"]:
            # guards keep the match out of just-inserted tags ("<volume>2022")
            text, n = re.subn(r"(?<![>\d])" + re.escape(a["year"]) + r"(?![\d<])",
                              f"<year>{a['year']}</year>", text, count=1)
            if n:
                done["year"] = True
        if a["issue"] and not done["no"]:
            esc_issue = re.escape(a["issue"]).replace(r"\ ", r"\s*")
            text, n = re.subn(r"(nos?\.\s*)" + esc_issue,
                              rf"\1<issue>{a['issue']}</issue>", text,
                              count=1, flags=re.IGNORECASE)
            if n:
                done["no"] = True
        if a["fpage"] and not done["pp"]:
            if a["lpage"]:
                pat = (r"(pp\.\s*)" + re.escape(a["fpage"]) +
                       r"(\s*[–‒—-]\s*)" + re.escape(a["lpage"]))
                rep = rf"\1<fpage>{a['fpage']}</fpage>\2<lpage>{a['lpage']}</lpage>"
            else:
                pat = r"(p\.\s*)" + re.escape(a["fpage"]) + r"\b"
                rep = rf"\1<fpage>{a['fpage']}</fpage>"
            text, n = re.subn(pat, rep, text, count=1)
            if n:
                done["pp"] = True
        return _linkify_text(text, citation=True)

    parts = _TAG_SPLIT_RE.split(tail_xml)
    return "".join(p if p.startswith("<") else wrap_text(p) for p in parts)


def build_mixed_citation(html_str, prev_author_text=""):
    """One Works Cited entry (editor HTML) -> (<mixed-citation> XML,
    analysis dict). All printed text is preserved in order."""
    a = analyze_ref(html_str, prev_author_text)
    toks = a["tokens"]

    def ser(lo, hi):
        return tokens_to_jats(toks[lo:hi])

    parts = []
    if a["body_start_tok"]:
        prefix = ser(0, a["body_start_tok"])
        if a["people"] and a["author_text"]:
            prefix = _wrap_names(prefix, a["people"], a["person_group_type"])
        parts.append(prefix)

    cur = a["body_start_tok"]
    tail_segments = []
    if a["title_lo"] is not None:
        tail_segments.append(("plain", cur, a["title_lo"]))     # incl. open quote
        tail_segments.append(("title", a["title_lo"], a["title_hi"]))
        cur = a["title_hi"]                                     # close quote stays plain
    if a["source_lo"] is not None and a["source_lo"] >= cur:
        tail_segments.append(("plain", cur, a["source_lo"]))
        tail_segments.append(("source", a["source_lo"], a["source_hi"]))
        cur = a["source_hi"]
    tail_segments.append(("plain", cur, len(toks)))

    tail = []
    for kind, lo, hi in tail_segments:
        seg = ser(lo, hi)
        if not seg:
            continue
        if kind == "title":
            # match the element-citation: chapters use <chapter-title>
            t_el = "chapter-title" if a["ptype"] == "chapter" else "article-title"
            seg = f"<{t_el}>{seg}</{t_el}>"
        elif kind == "source":
            seg = f"<source>{seg}</source>"
        else:
            # year/vol/pages/DOI tags belong in the loose text only -- never
            # inside the quoted title or the italic source
            seg = _micro_wrap_tail(seg, a)
        tail.append(seg)
    parts.append("".join(tail))

    xml = (f'<mixed-citation publication-type="{esc_attr(a["ptype"])}">'
           + "".join(parts) + "</mixed-citation>")
    return xml, a


def _strip_trailing_period(xml_text):
    return re.sub(r"\.((?:</[a-z-]+>)*)\s*$", r"\1", xml_text)


def build_element_citation(a, profile=None):
    """Fully structured <element-citation> from an analyze_ref() result.

    In the "lens" profile this is the citation OJS's eLife/Lens viewer
    actually renders, which requires bending several fields (see
    bcs_profiles.py). In the "archival" profile it is plain correct JATS.

    Note that <name> (rather than <string-name>) is used in both profiles:
    inside a structured <element-citation>, <name> is the correct JATS
    element for a parsed personal name. That one is not a workaround.
    """
    from bcs_editor import tokens_to_jats
    profile = get_profile(profile) if profile is not None else DEFAULT_PROFILE
    toks = a["tokens"]
    elems = []

    def _polish_given(g):
        # a trailing bare initial reads better with its period: "Michael G."
        return g + "." if re.search(r"\b[A-Z]$", g) else g

    if a["people"]:
        names = "".join(
            f"<name><surname>{esc(s)}</surname>"
            + (f"<given-names>{esc(_polish_given(g))}</given-names>" if g else "")
            + "</name>"
            for s, g in a["people"])
        if a["etal"]:
            names += "<etal/>"
        elems.append(f'<person-group person-group-type="{esc_attr(a["person_group_type"])}">'
                     f"{names}</person-group>")
    elif a.get("collab"):
        # institutional author -- Lens reads <collab> and shows it as the
        # citation's author line
        elems.append('<person-group person-group-type="author">'
                     f'<collab>{esc(a["collab"])}</collab></person-group>')
    elif profile.anonymous_placeholder:
        # Lens skips any citation without a person-group -- an <anonymous/>
        # placeholder keeps author-less refs (films, websites...) visible.
        # NOT TRUE of the works themselves; omitted in the archival profile.
        elems.append('<person-group person-group-type="author"><anonymous/></person-group>')

    # Lens renders only these citation fields: title, authors, source/volume,
    # pages, year, publisher and a DOI link. Sibling <ext-link> elements are
    # dropped (Lens's citation_urls list is never populated by its converter),
    # so a plain URL would vanish from the displayed reference. The one field
    # rendered as *annotated text* -- where an embedded <ext-link> becomes a
    # real hyperlink -- is the title, which Lens takes from <article-title>,
    # falling back to <comment>, then <source>. So: hyperlink the title text
    # with the ref's URL (text content is unchanged, harmless to aggregators);
    # when there is no title, put the link inside <comment> instead. The
    # standalone <ext-link> sibling is still emitted below for aggregators.
    link_url = a["urls"][0] if a["urls"] else ""
    link_used = False

    source_text = ""
    if a["source_lo"] is not None:
        source_text = "".join(t["t"] for t in toks[a["source_lo"]:a["source_hi"]])
        source_text = " ".join(source_text.split()).strip().rstrip(".,;: ")

    # Title elements. Two viewers read two different things, so emit both
    has_own_title = a["title_lo"] is not None
    if has_own_title:
        title_xml = _strip_trailing_period(
            tokens_to_jats(toks[a["title_lo"]:a["title_hi"]]).strip())
        container_text = source_text          # journal / anthology / newspaper
    else:
        title_xml = esc(source_text)          # the italic text IS the title
        container_text = "" if profile.whole_work_title_as_article_title else source_text

    if profile.whole_work_title_as_article_title:
        # --- lens: everything titled goes through <article-title> ------------
        if title_xml:
            linked_title = title_xml
            if profile.hyperlink_citation_title and link_url and "<ext-link" not in title_xml:
                linked_title = (f'<ext-link ext-link-type="uri" '
                                f'xlink:href="{esc_attr(link_url)}">'
                                f"{title_xml}</ext-link>")
                link_used = True
            elems.append(f"<article-title>{linked_title}</article-title>")
            if a["ptype"] == "chapter":
                # plain copy for Back/Chapter.php -- one hyperlink per ref is enough
                elems.append(f"<chapter-title>{title_xml}</chapter-title>")
        if container_text:
            elems.append(f"<source>{esc(container_text)}</source>")
    else:
        # --- archival: correct JATS -----------------------------------------
        # A part-of-a-whole (article in a journal, chapter in a book) gets a
        # part title; the container goes in <source>. A whole work (book,
        # film, standalone site) has no part title at all -- its own title
        # IS the <source>.
        if has_own_title and title_xml:
            part_el = "chapter-title" if a["ptype"] == "chapter" else "article-title"
            elems.append(f"<{part_el}>{title_xml}</{part_el}>")
        if container_text:
            elems.append(f"<source>{esc(container_text)}</source>")
    if a["year"]:
        elems.append(f"<year>{esc(a['year'])}</year>")
    if a["volume"]:
        elems.append(f"<volume>{esc(a['volume'])}</volume>")
    if a["issue"]:
        elems.append(f"<issue>{esc(a['issue'])}</issue>")
    if a["fpage"]:
        elems.append(f"<fpage>{esc(a['fpage'])}</fpage>")
    if a["lpage"]:
        elems.append(f"<lpage>{esc(a['lpage'])}</lpage>")
    if a["publisher"]:
        elems.append(f"<publisher-name>{esc(a['publisher'])}</publisher-name>")
    if a["doi"]:
        elems.append(f'<pub-id pub-id-type="doi">{esc(a["doi"])}</pub-id>')
    for url in a["urls"]:
        e = esc(url)
        elems.append(f'<ext-link ext-link-type="uri" xlink:href="{e}">{e}</ext-link>')

    comment_xml = esc(a["comment"]) if a.get("comment") else ""
    if profile.url_into_comment and link_url and not link_used:
        # no linkable title: Lens will fall back to <comment> for its display
        # title, so carry the clickable URL there ("Available from" pattern)
        link_el = (f'<ext-link ext-link-type="uri" '
                   f'xlink:href="{esc_attr(link_url)}">{esc(link_url)}</ext-link>')
        comment_xml = f"{comment_xml}, {link_el}" if comment_xml else link_el
    if comment_xml:
        elems.append(f"<comment>{comment_xml}</comment>")

    return (f'<element-citation publication-type="{esc_attr(a["ptype"])}">'
            + "".join(elems) + "</element-citation>")


_SPAN_PRESENTATION_RE = re.compile(
    r'<span\b(?:[^>]*\bclass="sc"[^>]*|[^>]*\bdata-style-type=[^>]*)>(.*?)</span>', re.S)


def render_ref_lists(project, warnings, profile=None):
    profile = get_profile(profile) if profile is not None else DEFAULT_PROFILE
    groups_xml = []
    ref_rows = []
    for g_idx, group in enumerate(project.get("ref_groups", []), start=1):
        if not group["refs"]:
            continue
        refs_xml = []
        prev_author = ""
        skipped_empty = 0
        for r in group["refs"]:
            # an empty entry (a stray blank line in the reference list) would
            # become an empty <element-citation>, which the DTD rejects
            if not re.sub(r"<[^>]+>|&nbsp;|\s", "", r.get("html") or ""):
                skipped_empty += 1
                continue
            rid = r.get("id") or f"cit{g_idx}x{len(refs_xml)}"
            # Small caps and special-character spans are presentation; inside
            # a <mixed-citation> they would end up wrapped around
            # <string-name>, which the DTD does not allow. Drop the spans and
            # keep their text.
            html_str = _SPAN_PRESENTATION_RE.sub(r"\1", r["html"])
            mixed_xml, a = build_mixed_citation(html_str, prev_author)
            prev_author = a["resolved_author_text"]
            # BOTH citation forms per ref: the structured element-citation is
            # what the eLife/Lens viewer displays (authors included); the
            # mixed-citation carries the exact printed text for aggregators
            # (Lens ignores it, since it has no person-group).
            elem_xml = build_element_citation(a, profile)
            refs_xml.append(f'<ref id="{esc_attr(rid)}">{elem_xml}{mixed_xml}</ref>')
            confidence = sum([bool(a["year"]),
                              a["title_lo"] is not None or a["source_lo"] is not None,
                              bool(a["people"])])
            ref_rows.append({"id": rid, "text": " ".join(a["plain"].split())[:90],
                             "confidence": confidence})
        if skipped_empty:
            warnings.append(f"{skipped_empty} empty entr{'y was' if skipped_empty == 1 else 'ies were'} "
                            f"in the reference list and left out -- delete {'it' if skipped_empty == 1 else 'them'} in the References tab.")
        if not refs_xml:
            continue
        title = esc(" ".join(group["title"].split()) or "Works Cited")
        groups_xml.append(f'<ref-list id="refs{g_idx}"><title>{title}</title>'
                          + "".join(refs_xml) + "</ref-list>")
    if not groups_xml:
        return "", ref_rows
    if project.get("bibliography") and len(groups_xml) >= 1:
        return ('<ref-list id="bibliography"><title>Bibliography</title>'
                + "".join(groups_xml) + "</ref-list>"), ref_rows
    return "".join(groups_xml), ref_rows


# ---------------------------------------------------------------------------
# body: nested <sec> from headings, verse grouping, etc.
# ---------------------------------------------------------------------------

_GRAPHIC_MIME = {
    "jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif",
    "tif": "tiff", "tiff": "tiff", "svg": "svg+xml", "webp": "webp",
    "bmp": "bmp", "eps": "postscript",
}


def _graphic_mime_subtype(filename):
    """Map an image filename's extension to a JATS mime-subtype."""
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    return _GRAPHIC_MIME.get(ext, "jpeg")


def render_figure(b, fig_id, warnings):
    """Render a 'figure' block as a JATS <fig>.

    The graphic href is ALWAYS a bare filename (e.g. figure1.jpg) -- never a
    hardcoded OJS/eLife download URL.
    Upload each image in OJS as a DEPENDENT FILE of the HTML galley, with its
    Name set to exactly this filename (case-sensitive, including extension).
    """
    filename = (b.get("file") or "").strip()
    label = (b.get("label") or "").strip()
    alt = (b.get("alt") or "").strip()
    position = (b.get("position") or "float").strip() or "float"

    parts = [f'<fig id="{esc_attr(fig_id)}" position="{esc_attr(position)}">']
    if label:
        parts.append(f"<label>{esc(label)}</label>")

    caption_inner = linkify_urls(editor_html_to_jats(b.get("html", "")))
    caption_title = (b.get("caption_title") or "").strip()
    if caption_title or caption_inner:
        cap = "<caption>"
        if caption_title:
            cap += f"<title>{esc(caption_title)}</title>"
        if caption_inner:
            cap += f"<p>{caption_inner}</p>"
        cap += "</caption>"
        parts.append(cap)

    if alt:
        parts.append(f"<alt-text>{esc(alt)}</alt-text>")

    if filename:
        subtype = _graphic_mime_subtype(filename)
        parts.append(
            f'<graphic xlink:href="{esc_attr(filename)}" '
            f'mimetype="image" mime-subtype="{subtype}"/>'
        )
        # InDesign links print files (.tif, .eps, .psd, .ai), often with
        # spaces in the name. Browsers can't show those, and OJS matches
        # dependent files by exact name.
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("jpg", "jpeg", "png", "gif", "webp", "svg"):
            warnings.append(
                f"Figure {label or fig_id!r}: {filename!r} is a print file "
                "browsers can't show. Export a .jpg or .png, attach that to "
                "the HTML galley, and type its name here."
            )
        if " " in filename:
            warnings.append(
                f"Figure {label or fig_id!r}: the filename has spaces. Rename "
                "the image (e.g. fig1.jpg) before attaching it in OJS, and "
                "type the new name here."
            )
    else:
        warnings.append(
            f"Figure {label or fig_id!r} has no image filename. "
            "Type the exact filename of the image you will "
            "attach to the HTML galley."
        )

    parts.append("</fig>")
    return "".join(parts)


# Audio the browser can play in an <audio> player. The pair is the JATS
# mimetype / mime-subtype, which the HTML stylesheet turns back into a type.
AUDIO_MIME = {
    "mp3": "mpeg", "m4a": "mp4", "aac": "aac", "wav": "wav",
    "ogg": "ogg", "oga": "ogg", "opus": "ogg", "flac": "flac", "webm": "webm",
}


def render_audio(b, aud_id, warnings):
    """Render an 'audio' block as a JATS <media mimetype="audio">.

    Like a figure, the href is a bare filename (e.g. hot-topic-ep1.mp3). In
    OJS, upload the file as a DEPENDENT FILE of the HTML galley with its
    Name set to exactly this filename. The HTML stylesheet turns it into a player.
    """
    filename = (b.get("file") or "").strip()
    label = (b.get("label") or "").strip()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    name = label or aud_id
    if not filename:
        # <media> requires an href, so a clip with no file is left out
        warnings.append(f"Audio clip {name!r} has no filename and was left out of "
                        "the XML. Upload the file in the Body tab or type the exact "
                        "filename you will attach in OJS.")
        return ""
    if ext not in AUDIO_MIME:
        warnings.append(f"Audio clip {name!r}: {filename!r} is not a type browsers "
                        "play reliably. Use an MP3 (or M4A).")

    parts = [f'<media id="{esc_attr(aud_id)}" position="anchor" mimetype="audio" '
             f'mime-subtype="{AUDIO_MIME.get(ext, "mpeg")}" '
             f'xlink:href="{esc_attr(filename)}">']
    if label:
        parts.append(f"<label>{esc(label)}</label>")
    caption_inner = linkify_urls(editor_html_to_jats(b.get("html", "")))
    caption_title = (b.get("caption_title") or "").strip()
    if caption_title or caption_inner:
        parts.append("<caption>"
                     + (f"<title>{esc(caption_title)}</title>" if caption_title else "")
                     + (f"<p>{caption_inner}</p>" if caption_inner else "")
                     + "</caption>")
    parts.append("</media>")
    return "".join(parts)


def audio_ids(project):
    """The id of every audio block, in order, never duplicated."""
    ids, used, n = [], set(), 0
    for b in project.get("blocks", []):
        if b.get("kind") != "audio":
            continue
        n += 1
        aid = (b.get("id") or "").strip() or f"aud-{n}"
        while aid in used:
            aid = f"{aid}x"
        used.add(aid)
        ids.append(aid)
    return ids


def figure_ids(project):
    """The id of every figure block in order. Ids are stored on the block
    (b["id"]) so in-text <xref ref-type="fig"> targets stay stable when
    figures are moved around; older drafts without ids fall back to fig-N."""
    ids, used, n = [], set(), 0
    for b in project.get("blocks", []):
        if b.get("kind") != "figure":
            continue
        n += 1
        fid = (b.get("id") or "").strip() or f"fig-{n}"
        while fid in used:                      # never emit a duplicate id
            fid = f"{fid}x"
        used.add(fid)
        ids.append(fid)
    return ids


def table_ids(project):
    """The id of every table block, in order, never duplicated."""
    ids, used, n = [], set(), 0
    for b in project.get("blocks", []):
        if b.get("kind") != "table":
            continue
        n += 1
        tid = (b.get("id") or "").strip() or f"tbl-{n}"
        while tid in used:
            tid = f"{tid}x"
        used.add(tid)
        ids.append(tid)
    return ids


def render_table(b, tbl_id, warnings):
    """Render a 'table' block as a JATS <table-wrap>.

    The label ("Table 1") and caption go in <label> and <caption>, the rows
    in <thead>/<tbody> -- the first header_rows rows are the head -- and any
    source or note text under the table in <table-wrap-foot>. Older drafts
    that still carry a finished JATS string (no "rows") pass it through."""
    label = (b.get("label") or "").strip()
    head = f"<label>{esc(label)}</label>" if label else ""
    if "rows" not in b:
        caption = b.get("caption", "")
        if caption:
            head += f"<caption><p>{editor_html_to_jats(caption)}</p></caption>"
        return f'<table-wrap id="{tbl_id}">{head}{b.get("html", "")}</table-wrap>'

    caption = _paras_to_jats(b.get("html", ""))
    if caption:
        head += f"<caption>{caption}</caption>"
    rows = [r for r in b.get("rows") or [] if r]
    if not rows:
        warnings.append(f"{label or 'A table'} has no rows and was left out of "
                        "the XML -- fill it in or delete it in the Body tab.")
        return ""

    def row_xml(row, in_head):
        cells = []
        for c in row:
            tag = "th" if in_head or c.get("th") else "td"
            attrs = ""
            for k in ("colspan", "rowspan"):
                try:
                    v = int(c.get(k) or 1)
                except (TypeError, ValueError):
                    v = 1
                if v > 1:
                    attrs += f' {k}="{v}"'
            inner = linkify_urls(editor_html_to_jats(c.get("html", "")))
            cells.append(f"<{tag}{attrs}>{inner}</{tag}>")
        return "<tr>" + "".join(cells) + "</tr>"

    n_head = max(0, min(int(b.get("header_rows") or 0), len(rows)))
    if n_head == len(rows):
        n_head = len(rows) - 1          # a <tbody> needs at least one row
    parts = [f'<table-wrap id="{tbl_id}">{head}<table frame="hsides" rules="groups">']
    if n_head:
        parts.append("<thead>" + "".join(row_xml(r, True) for r in rows[:n_head])
                     + "</thead>")
    parts.append("<tbody>" + "".join(row_xml(r, False) for r in rows[n_head:])
                 + "</tbody></table>")
    foot = _paras_to_jats(b.get("foot_html", ""))
    if foot:
        parts.append(f"<table-wrap-foot>{foot}</table-wrap-foot>")
    parts.append("</table-wrap>")
    return "".join(parts)


def render_body_blocks(project, warnings):
    root = []
    sec_stack = []       # [{"level": n, "title": xml, "parts": [], "id": "secN"}]
    sec_counter = 0
    fig_counter = 0
    fig_ids = figure_ids(project)
    tbl_counter = 0
    tbl_ids = table_ids(project)
    aud_counter = 0
    aud_ids = audio_ids(project)
    stanza, stanzas = [], []

    def target():
        return sec_stack[-1]["parts"] if sec_stack else root

    def flush_verse():
        nonlocal stanza, stanzas
        if stanza:
            stanzas.append(stanza)
            stanza = []
        for st in stanzas:
            target().append("<verse-group>"
                            + "".join(f"<verse-line>{l}</verse-line>" for l in st)
                            + "</verse-group>")
        stanzas = []

    def close_sec():
        s = sec_stack.pop()
        xml = (f'<sec id="{s["id"]}"><title>{s["title"]}</title>'
               + "".join(s["parts"]) + "</sec>")
        target().append(xml)

    for b in project.get("blocks", []):
        kind = b.get("kind", "p")
        if kind == "verse":
            stanza.append(editor_html_to_jats(b.get("html", "")))
            continue
        if kind == "verse-break":
            if stanza:
                stanzas.append(stanza)
                stanza = []
            continue
        flush_verse()

        if kind == "figure":
            fig_id = fig_ids[fig_counter]
            fig_counter += 1
            target().append(render_figure(b, fig_id, warnings))
            continue

        if kind == "audio":
            aud_id = aud_ids[aud_counter]
            aud_counter += 1
            xml = render_audio(b, aud_id, warnings)
            if xml:
                target().append(xml)
            continue

        if kind == "heading":
            level = max(1, min(3, int(b.get("level") or 1)))
            while sec_stack and sec_stack[-1]["level"] >= level:
                close_sec()
            sec_counter += 1
            sec_stack.append({"level": level, "parts": [],
                              "title": editor_html_to_jats(b.get("html", "")),
                              "id": f"sec{sec_counter}"})
            continue

        inner = linkify_urls(editor_html_to_jats(b.get("html", "")))
        if kind == "p":
            target().append(f"<p>{inner}</p>")
        elif kind == "blockquote":
            target().append(f"<disp-quote><p>{inner}</p></disp-quote>")
        elif kind == "epigraph":
            target().append(f'<disp-quote content-type="epigraph"><p>{inner}</p></disp-quote>')
        elif kind == "epigraph-source":
            target().append(f'<p content-type="epigraph-source">{inner}</p>')
        elif kind == "fig-caption":
            target().append(f"<fig><caption><p>{inner}</p></caption></fig>")
        elif kind == "divider":
            target().append(f'<p content-type="divider">{inner or "&#8226;"}</p>')
        elif kind == "table":
            tbl_id = tbl_ids[tbl_counter]
            tbl_counter += 1
            xml = render_table(b, tbl_id, warnings)
            if xml:
                target().append(xml)
        else:
            warnings.append(f"Unknown block kind {kind!r} rendered as a paragraph.")
            target().append(f"<p>{inner}</p>")

    flush_verse()
    while sec_stack:
        close_sec()
    return root


def render_notes_sec(project):
    """Endnotes as a visible <sec> at the end of the body (like the print
    journal). The OJS eLife/Lens plugin never displays a back-matter
    <fn-group> (its extractNotes hook is an empty stub), so this is the only
    placement that shows up in OJS -- and for aggregators it reads exactly
    like the printed Notes section. In-text callouts keep their
    <xref ref-type="fn" rid="fnN"> pointing at each note's paragraph id.

    Used by the "lens" profile. See render_notes_fn_group() for the archival
    equivalent."""
    notes = project.get("notes", [])
    if not notes:
        return ""
    parts = []
    for i, note in enumerate(notes, start=1):
        for j, part in enumerate(note.get("parts", [])):
            xml_text = linkify_urls(editor_html_to_jats(part.get("html", "")))
            if part.get("kind") == "q":
                parts.append(f"<disp-quote><p>{xml_text}</p></disp-quote>")
            elif j == 0:
                parts.append(f'<p id="fn{i}" content-type="endnote">'
                             f"<sup>{i}</sup>&#160;{xml_text}</p>")
            else:
                parts.append(f"<p>{xml_text}</p>")
    return ('<sec id="notes" sec-type="endnotes"><title>Notes</title>'
            + "".join(parts) + "</sec>")


def render_notes_back_fn_group(project):
    """Endnotes as a <fn-group> in <back> -- the correct JATS home for them.

    Used by the "archival" profile. The in-text callouts are unchanged:
    <xref ref-type="fn" rid="fnN"> now resolves to the <fn> itself rather
    than to its first paragraph, so the links still work."""
    notes = project.get("notes", [])
    if not notes:
        return ""
    fns = []
    for i, note in enumerate(notes, start=1):
        parts = []
        for part in note.get("parts", []):
            xml_text = linkify_urls(editor_html_to_jats(part.get("html", "")))
            if part.get("kind") == "q":
                parts.append(f"<disp-quote><p>{xml_text}</p></disp-quote>")
            else:
                parts.append(f"<p>{xml_text}</p>")
        fns.append(f'<fn id="fn{i}" fn-type="other"><label>{i}</label>'
                   + "".join(parts) + "</fn>")
    return f'<fn-group content-type="endnotes"><title>Notes</title>{"".join(fns)}</fn-group>'


# ---------------------------------------------------------------------------
# full article
# ---------------------------------------------------------------------------

def _license_xml(meta, year, warnings):
    """The <license> under <permissions>, which is also what the galley's
    "Rights and permissions" button links to.

    An article is published under one of two things: the Creative
    Commons licence (BC Studies, 2027 onward) or the journal's own copyright
    agreement (everything in the archive). Blank -- which is how every article
    arrives from the importer -- decides on the article's own year, so the
    archive is not retro-fitted with a licence it never had. The Metadata
    tab's "rights" field overrides that for the odd article that needs it.

    Both come out as <license>, which is correct JATS -- @license-type says
    which, and the galley reads that attribute to label the button. The
    copyright agreement is always written, with or without an address; only
    a CC article with LICENSE["url"] blanked out returns ""."""
    y = _int_year(year)
    chosen_by_hand = (meta.get("rights") or "").strip().lower()
    if chosen_by_hand and chosen_by_hand not in ("cc", "copyright"):
        warnings.append(f"Rights is set to {chosen_by_hand!r}, which is not "
                        "\"cc\" or \"copyright\" -- the article's year was "
                        "used to decide instead.")
        chosen_by_hand = ""

    if chosen_by_hand:
        choice = chosen_by_hand
    elif CC_FROM_YEAR and y:
        choice = "cc" if y >= CC_FROM_YEAR else "copyright"
    else:
        choice = RIGHTS_DEFAULT

    if choice == "cc":
        # An article cannot have been published under a licence the journal
        # did not use yet. Say so instead of stamping the badge on it.
        if CC_FROM_YEAR and y and y < CC_FROM_YEAR:
            warnings.append(
                f"Rights is set to \"cc\" by hand, but this article is dated "
                f"{y} and BC Studies only publishes under a Creative Commons "
                f"licence from {CC_FROM_YEAR}. Clear the Rights field unless "
                "this one really is CC licensed.")
        if not LICENSE.get("url"):
            return ""
        return (f'<license license-type="open-access" '
                f'xlink:href="{esc_attr(LICENSE["url"])}">'
                f'<license-p>{esc(LICENSE.get("text") or "")}</license-p></license>')

    # The copyright agreement always gets its <license>, and so always gets
    # the "Rights and permissions" button. With no address set, the button
    # shows the text alone; once COPYRIGHT_AGREEMENT["url"] is filled in, the
    # link to the policy appears under it.
    url = (COPYRIGHT_AGREEMENT.get("url") or "").strip()
    href = f' xlink:href="{esc_attr(url)}"' if url else ""
    return (f'<license license-type="copyright"{href}>'
            f'<license-p>{esc(COPYRIGHT_AGREEMENT.get("text") or "")}</license-p></license>')


def _int_year(year):
    try:
        return int(str(year).strip())
    except (TypeError, ValueError):
        return None


# A capital letter inside a word that no ordinary spelling would put there.
# Ordinary: the name particles below ("McLoughlin", "LeBlanc", "VanderZalm"),
# an apostrophe ("O'Brien", "d'Arcy"), a hyphen ("Re-Entry"), and a single
# lowercase letter in front ("eLife", "iPhone"). "ReLationship" is none of
# those.....
_ODD_CAPS = re.compile(r"(?<=[a-z])[A-Z]")
_NAME_PARTICLES = ("Mac", "Mc", "Fitz", "Vander", "Van", "Von", "De", "Di",
                   "Du", "Da", "La", "Le", "Lo", "O")
_ODD_CAPS_OK = re.compile(
    r"^(?:" + "|".join(_NAME_PARTICLES) + r")(?=[A-Z])"
    r"|^[a-z](?=[A-Z])"
    r"|['’](?=[A-Za-z])", re.UNICODE)
# Degrees and the like, which are spelled with an interior capital.
_ODD_CAPS_WORDS_OK = {"phd", "edd", "scd", "littd", "dphil", "llb", "llm",
                      "lld", "mphil", "bsc", "msc", "mfa", "mba"}


def _odd_caps_words(text):
    """Words holding a stray interior capital, e.g. "ReLationship".

    InDesign's Capitalization="AllCaps" is a display setting: it draws the
    text in capitals without changing the characters underneath. A heading
    typed "ReLationship" therefore looks perfectly correct in the printed
    journal and stays wrong in the file. Nobody can catch that by proofreading
    the page, so the tool looks for it instead."""
    out = []
    for word in re.findall(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", text or "",
                           flags=re.UNICODE):
        if word.isupper() or word.islower():
            continue
        if word.lower() in _ODD_CAPS_WORDS_OK:
            continue
        # break the word at every spelling that legitimately carries an
        # interior capital, then see if a capital is still stranded after a
        # lowercase letter
        stripped = _ODD_CAPS_OK.sub(" ", word)
        stripped = re.sub(r"[-‐-―'’]", " ", stripped)
        if _ODD_CAPS.search(stripped):
            out.append(word)
    return out


def check_odd_caps(project, warnings):
    """Warn about stray interior capitals in the title, subtitle and headings
    -- the places a reader meets first and the places the sidebar Outline
    repeats, so one typo shows up twice."""
    meta = project.get("meta", {})
    places = [("the title", title_plain(meta.get("title", ""))),
              ("the subtitle", title_plain(meta.get("subtitle", "")))]
    for b in project.get("blocks", []):
        if b.get("kind") == "heading":
            places.append(("a heading", re.sub(r"<[^>]+>", "", b.get("html", ""))))
    for where, text in places:
        for word in _odd_caps_words(text):
            warnings.append(
                f"{word!r} in {where} has a capital letter inside the word. "
                "InDesign draws a heading in capitals without changing the "
                "characters... so a typo like this is invisible on the printed "
                "page. Check it against the manuscript before publishing.")


def build_provenance_meta(project, profile):
    """A <custom-meta-group> describing how this file was made."""
    items = [
        ("generator", f"bcs-jats-tool {TOOL_VERSION}"),
        ("generator-profile", profile.name),
        ("generator-profile-description", profile.description),
        ("generated", _today_iso()),
    ]
    src = (project.get("source_filename") or "").strip()
    if src:
        items.append(("source-document", src))
    for i, note in enumerate(profile.accommodations, start=1):
        items.append((f"profile-accommodation-{i}", note))
    if not profile.accommodations:
        items.append(("profile-accommodation",
                      "None. This file is rendered without viewer-specific "
                      "workarounds and is intended as the preservation copy."))
    metas = "".join(
        f"<custom-meta><meta-name>{esc(k)}</meta-name>"
        f"<meta-value>{esc(v)}</meta-value></custom-meta>"
        for k, v in items)
    return f"<custom-meta-group>{metas}</custom-meta-group>"


def _today_iso():
    from datetime import date
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# contributor bios: one box per contributor (Metadata tab)
# ---------------------------------------------------------------------------

def _name_key(text):
    """A name reduced for comparison: no accents, no punctuation, lower case,
    single spaces. The editor's nameKey() does the same thing in JS."""
    import unicodedata
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.category(c).startswith("M"))
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return " ".join(t.split())


def _bio_boxes(meta):
    """The Metadata tab's per-contributor boxes, [{"name", "html"}], without
    the empty ones. [] for a draft that has never used them -- those keep
    reading the single bios_html field exactly as before."""
    raw = meta.get("bios")
    if not isinstance(raw, list):
        return []
    out = []
    for box in raw:
        if not isinstance(box, dict):
            continue
        html_str = box.get("html") or ""
        if not re.sub(r"<[^>]+>|&nbsp;|\s", "", html_str):
            continue
        out.append({"name": " ".join(str(box.get("name") or "").split()),
                    "html": html_str})
    return out


def _match_bio_name(name, people):
    """Index of the byline author a box's name means, or None. The whole name
    first ("Jane Smith"), then the surname alone, if only one author has
    it. The editor's matchBioName() mirrors this."""
    key = _name_key(name)
    if not key:
        return None
    hits = [i for i, (s, g) in enumerate(people)
            if _name_key(f"{g} {s}") and _name_key(f"{g} {s}") == key]
    if len(hits) == 1:
        return hits[0]
    padded = f" {key} "
    hits = [i for i, (s, _g) in enumerate(people)
            if _name_key(s) and f" {_name_key(s)} " in padded]
    return hits[0] if len(hits) == 1 else None


def _assign_bio_boxes(boxes, people, warnings):
    """-> (bio_paras, assigned, unassigned) in the shape render_project's
    contributor loop already uses: a flat list of paragraph strings, one list
    of paragraph indexes per author, and the indexes nobody claimed."""
    bio_paras = []
    assigned = [[] for _ in people]
    unassigned = []
    for n, box in enumerate(boxes):
        paras = _split_paras(box["html"])
        idxs = list(range(len(bio_paras), len(bio_paras) + len(paras)))
        bio_paras.extend(paras)
        who = _match_bio_name(box["name"], people)
        if who is None and len(people) == 1 and len(boxes) == 1:
            who = 0                      # one author, one bio: nothing to decide
        if who is None and not _name_key(box["name"]) and len(boxes) == len(people):
            who = n                      # unnamed boxes follow the byline order
        if who is None:
            unassigned.extend(idxs)
            label = f"'{box['name']}'" if box["name"] else f"number {n + 1} (no name typed)"
            byline_names = ", ".join(" ".join(x for x in (g, s) if x) for s, g in people) or "none"
            warnings.append(
                f"Contributor bio {label} doesn't match an author in the Author(s) field "
                f"({byline_names}) -- it was kept in the article's author notes. "
                "Type the name as it appears in the byline in the Metadata tab.")
        else:
            assigned[who].extend(idxs)
    return bio_paras, assigned, unassigned


def render_project(project, profile=None):
    """Returns (xml_string, warnings, stats, ref_rows).

    profile: "lens" (default -- the HTML galley is built from it) or "archival" (clean JATS).
    See bcs_profiles.py for what differs and why."""
    profile = get_profile(profile) if profile is not None else DEFAULT_PROFILE
    warnings = []
    meta = project["meta"]
    section_info = section_lookup(meta.get("section", ""))
    seq = int(meta.get("seq") or 1)
    # title and subtitle are inline editor HTML: italics for a book or case name
    title_toks = title_tokens(meta.get("title") or "")
    title = tokens_plain(title_toks)
    check_odd_caps(project, warnings)

    # --- contributors -------------------------------------------------------
    # Bios go INSIDE each <contrib> as <bio>: that's where the eLife/Lens
    # viewer shows them (under the author's name in the Info tab), and it's
    # the semantically correct JATS placement for aggregators too.
    from bcs_names import split_byline as split_authors
    byline = " ".join((meta.get("authors") or "").split())
    people = split_authors(byline) if byline else []
    bio_boxes = _bio_boxes(meta)
    # the Metadata tab's per-contributor boxes, when a draft has them, are the
    # source of truth; older drafts keep reading the single field below
    bio_paras = [] if bio_boxes else _split_paras(meta.get("bios_html", ""))

    assigned = [[] for _ in people]
    unassigned_bios = []
    if len(people) == 1:
        assigned[0] = list(range(len(bio_paras)))
    elif people:
        for j, para in enumerate(bio_paras):
            plain = re.sub(r"<[^>]+>", "", para).lower()
            hits = [i for i, (s, _g) in enumerate(people) if s.lower() in plain]
            if len(hits) == 1:
                assigned[hits[0]].append(j)
            else:
                unassigned_bios.append(j)
                warnings.append("A contributor bio couldn't be matched to one author "
                                "by surname -- it was kept in the article's author notes.")
    else:
        unassigned_bios = list(range(len(bio_paras)))

    if bio_boxes:
        bio_paras, assigned, unassigned_bios = _assign_bio_boxes(bio_boxes, people, warnings)

    contribs = []
    aff = (meta.get("reviewer_affiliation") or "").strip()
    aff_xml = f"<aff>{esc(aff)}</aff>" if aff else ""
    orcids = _orcids(meta, len(people))
    if any(orcids) and len([o for o in re.split(r"\s+and\s+|\s*;\s*",
                                                 (meta.get("orcids") or "").strip()) if o.strip()]) > len(people):
        warnings.append("More ORCIDs than authors in the Metadata tab -- the extra ones were ignored.")
    for i, (surname, given) in enumerate(people):
        bio_xml = ""
        if assigned[i]:
            bio_ps = "".join(
                f"<p>{linkify_urls(editor_html_to_jats(bio_paras[j]))}</p>"
                for j in assigned[i])
            bio_xml = f"<bio>{bio_ps}</bio>"
        # JATS puts contrib-id before name; OJS and Crossref both read it
        orcid_xml = (f'<contrib-id contrib-id-type="orcid">https://orcid.org/{esc(orcids[i])}</contrib-id>'
                     if orcids[i] else "")
        contribs.append(
            f'<contrib contrib-type="author">{orcid_xml}<name><surname>{esc(surname)}</surname>'
            + (f"<given-names>{esc(given)}</given-names>" if given else "")
            + f"</name>{aff_xml}{bio_xml}</contrib>")
    contrib_group_xml = f"<contrib-group>{''.join(contribs)}</contrib-group>" if contribs else ""

    # --- back matter first (refs referenced from body) -----------------------
    ref_list_xml, ref_rows = render_ref_lists(project, warnings, profile)
    ack_xml = ""
    ack_paras = _paras_to_jats(meta.get("ack_html", ""))
    if ack_paras:
        ack_xml = f"<ack>{ack_paras}</ack>"
    # JATS has no element of its own for an ethics statement (research-ethics
    # board approval and the like). A typed <notes> in the back matter is the
    # usual home, and says what it is to anyone reading notes-type.
    ethics_xml = ""
    ethics_paras = _paras_to_jats(meta.get("ethics_html", ""))
    if ethics_paras:
        ethics_xml = (f'<notes notes-type="ethics-statement">'
                      f"<title>Ethics Statement</title>{ethics_paras}</notes>")
    # notes live in <back> for the archival profile, in <body> for lens
    back_notes_xml = "" if profile.notes_in_body else render_notes_back_fn_group(project)
    back_inner = ack_xml + ethics_xml + back_notes_xml + ref_list_xml
    back_xml = f"<back>{back_inner}</back>" if back_inner else ""

    # --- body ----------------------------------------------------------------
    body_parts = render_body_blocks(project, warnings)
    book_info = _paras_to_jats(meta.get("book_info_html", ""))
    if book_info:
        body_parts.insert(0, f'<boxed-text content-type="book-info">{book_info}</boxed-text>')
    notes_sec_xml = render_notes_sec(project) if profile.notes_in_body else ""
    if notes_sec_xml:
        body_parts.append(notes_sec_xml)
    body_xml = "<body>" + "".join(body_parts) + "</body>" if body_parts else "<body><p/></body>"

    # --- author notes (byline as printed + any unmatched bios) ----------------
    notes_paras = []
    if "(" in byline:
        notes_paras.append(f"<p>Byline as printed: {esc(byline)}</p>")
    for j in unassigned_bios:
        notes_paras.append(f"<p>{linkify_urls(editor_html_to_jats(bio_paras[j]))}</p>")
    author_notes_xml = ""
    if notes_paras:
        author_notes_xml = ('<author-notes><fn fn-type="other">'
                            + "".join(notes_paras) + "</fn></author-notes>")

    # --- abstract + keywords --------------------------------------------------
    abstract_xml = ""
    abs_paras = _paras_to_jats(meta.get("abstract_html", ""))
    if abs_paras:
        abstract_xml = f"<abstract>{abs_paras}</abstract>"
    kwd_xml = ""
    keywords = [k for k in (meta.get("keywords") or []) if k.strip()]
    if keywords:
        kwds = "".join(f"<kwd>{esc(k.strip())}</kwd>" for k in keywords)
        kwd_xml = f'<kwd-group kwd-group-type="author"><title>Keywords</title>{kwds}</kwd-group>'

    # Funding sits in article-meta, where Crossref and the indexes look for
    # it. The statement is kept as printed, one <funding-statement> per
    # paragraph; funders and grant numbers are not broken out into
    # <award-group>, because the printed text does not reliably separate them.
    funding_xml = ""
    funding_statements = _paras_to_jats(meta.get("funding_html", ""),
                                        wrap="funding-statement")
    if funding_statements:
        funding_xml = f"<funding-group>{funding_statements}</funding-group>"

    issn_xml = ""
    if JOURNAL["issn_ppub"]:
        issn_xml += f'<issn pub-type="ppub">{JOURNAL["issn_ppub"]}</issn>'
    if JOURNAL["issn_epub"]:
        issn_xml += f'<issn pub-type="epub">{JOURNAL["issn_epub"]}</issn>'

    doi_xml = ""
    doi = (meta.get("doi") or "").strip()
    # strip whatever gets pasted around the DOI itself: "DOI: ", "doi:",
    # a doi.org URL, a trailing full stop
    doi = re.sub(r"^\s*(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", doi,
                 flags=re.I).rstrip(" .")
    if doi and not doi.startswith("10."):
        warnings.append(f"The DOI {doi!r} doesn't look right; it should start "
                        "with 10. Copy it from OJS.")
    if doi:
        doi_xml = f'<article-id pub-id-type="doi">{esc(doi)}</article-id>'

    fpage = (meta.get("fpage") or "").strip()
    lpage = (meta.get("lpage") or "").strip()
    fpage_xml = f"<fpage>{esc(fpage)}</fpage>" if fpage else ""
    lpage_xml = f"<lpage>{esc(lpage)}</lpage>" if lpage else ""

    year = (meta.get("year") or "").strip() or "UNKNOWN"
    issue_number = (meta.get("issue_number") or "").strip() or "UNKNOWN"

    # season sits before <year> inside <pub-date> (JATS: ((day?, month?) | season)?, year)
    season = (meta.get("season") or "").strip()
    season_xml = f"<season>{esc(season)}</season>" if season else ""

    # subtitle, kept separate from the title so the galley can set it on its
    # own line. The importer stores the title as printed ("Title: Subtitle")
    # and the subtitle beside it, so peel the subtitle off the end of the
    # title rather than printing it twice.
    sub_toks = title_tokens(meta.get("subtitle") or "")
    subtitle = tokens_plain(sub_toks)
    subtitle_xml = ""
    if subtitle and subtitle.lower() != title.lower():
        if title.lower().endswith(subtitle.lower()):
            head, cut = _split_at(title_toks, len(title) - len(subtitle))
            head = [dict(t) for t in head[:cut]] if cut is not None else []
            while head:
                head[-1]["t"] = head[-1]["t"].rstrip(" :\u2014\u2013-")
                if head[-1]["t"]:
                    break
                head.pop()
            if head:
                title_toks = head
        subtitle_xml = f"<subtitle>{tokens_to_jats(sub_toks)}</subtitle>"
    title_xml = tokens_to_jats(title_toks) or f"[UNTITLED PIECE {seq}]"

    # short title (running head)
    short_title = (meta.get("short_title") or "").strip()
    alt_title_xml = (f'<alt-title alt-title-type="running-head">{esc(short_title)}</alt-title>'
                     if short_title else "")
    # A review's galley is headed with the short title; the full title of
    # the book is in the book-info box below. With no short title typed, the
    # title up to its first colon is used ("Trading Fate: How a ..." ->
    # "Trading Fate"). Review essays keep their own title.
    if (not alt_title_xml and section_info["article-type"] == "book-review"
            and section_info["subject"] != "REVIEW ESSAY"):
        colon = title.find(": ")
        if colon > 0:
            head, cut = _split_at(title_toks, colon)
            # no footnote callouts in a heading-only copy of the title
            head = ([dict(t) for t in head[:cut] if t["fn"] is None]
                    if cut is not None else [])
            if tokens_plain(head).strip():
                alt_title_xml = (f'<alt-title alt-title-type="running-head">'
                                 f'{tokens_to_jats(head)}</alt-title>')

    editors_xml = _issue_editors_xml(meta)

    # Copyright stays with the author(s); the journal publishes under a
    # Creative Commons licence (both configurable in bcs_config.py).
    holder = (COPYRIGHT_HOLDER or "").strip() or _printed_authors(people, byline)
    copyright_xml = (f"<copyright-statement>&#169; {esc(holder)}, {esc(year)}</copyright-statement>"
                     f"<copyright-year>{esc(year)}</copyright-year>"
                     + (f"<copyright-holder>{esc(holder)}</copyright-holder>" if holder else ""))
    license_xml = _license_xml(meta, year, warnings)
    permissions_xml = f"<permissions>{copyright_xml}{license_xml}</permissions>"

    # Where else this article lives: the PDF galley and the article's landing
    # page on OJS. <self-uri> is the JATS element for "another address for
    # this same article", and article-meta allows it straight after
    # <permissions>. The galley's PDF and Share buttons are built from these.
    self_uri_xml = ""
    for field, content_type in (("pdf_url", "pdf"), ("article_url", "ojs")):
        url = (meta.get(field) or "").strip()
        if not url:
            continue
        if not re.match(r"^https?://", url, flags=re.I):
            warnings.append(f"{field} is {url!r}, which is not an http(s) address -- "
                            "it was left out of the XML.")
            continue
        self_uri_xml += (f'<self-uri content-type="{content_type}" '
                         f'xlink:href="{esc_attr(url)}"/>')

    # e-publication date: the galley's citation_publication_date (what
    # Google Scholar reads). It goes before the collection date so it is the
    # FIRST <pub-date>, which viewers take as the publication date. Accepts YYYY-MM-DD, YYYY-MM, or YYYY.
    epub_date_xml = ""
    epub_raw = (meta.get("epub_date") or "").strip()
    if epub_raw:
        m = re.match(r"^(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?$", epub_raw)
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            inner = ""
            if d:
                inner += f"<day>{int(d):02d}</day>"
            if mo:
                inner += f"<month>{int(mo):02d}</month>"
            inner += f"<year>{y}</year>"
            epub_date_xml = f'<pub-date pub-type="epub">{inner}</pub-date>'
        else:
            warnings.append(f"Could not read the e-publication date {epub_raw!r} -- "
                            "use YYYY-MM-DD (e.g. 2025-07-15). It was left out of the XML.")
    else:
        warnings.append("No e-publication date set (Metadata tab) -- the galley's "
                        "publication date for Google Scholar and other indexes falls "
                        "back to the issue year alone.")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Publishing DTD with MathML3 v1.4 20241031//EN" "https://jats.nlm.nih.gov/publishing/1.4/JATS-journalpublishing1-4-mathml3.dtd">
<article xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:mml="http://www.w3.org/1998/Math/MathML" article-type="{section_info['article-type']}" xml:lang="en">
<front>
<journal-meta>
<journal-id journal-id-type="publisher-id">{JOURNAL['journal_id']}</journal-id>
<journal-title-group><journal-title>{esc(JOURNAL['journal_title'])}</journal-title><abbrev-journal-title>{esc(JOURNAL['abbrev_title'])}</abbrev-journal-title></journal-title-group>
{issn_xml}
<publisher><publisher-name>{esc(JOURNAL['publisher_name'])}</publisher-name><publisher-loc>{esc(JOURNAL['publisher_loc'])}</publisher-loc></publisher>
</journal-meta>
<article-meta>
<article-id pub-id-type="publisher-id">{JOURNAL["id_prefix"]}-{esc(issue_number)}-{seq:02d}</article-id>
{doi_xml}
<article-categories><subj-group subj-group-type="heading"><subject>{esc(section_info['subject'])}</subject></subj-group></article-categories>
<title-group><article-title>{title_xml}</article-title>{subtitle_xml}{alt_title_xml}</title-group>
{contrib_group_xml}
{editors_xml}
{author_notes_xml}
{epub_date_xml}
<pub-date pub-type="collection">{season_xml}<year>{esc(year)}</year></pub-date>
<issue>{esc(issue_number)}</issue>
{fpage_xml}
{lpage_xml}
{permissions_xml}
{self_uri_xml}
{abstract_xml}
{kwd_xml}
{funding_xml}
{build_provenance_meta(project, profile)}
</article-meta>
</front>
{body_xml}
{back_xml}
</article>
"""

    stats = {
        "linked_citations": xml.count('ref-type="bibr"'),
        "unlinked_citations": _count_unlinked(project),
        "ext_links": xml.count("<ext-link"),
        "fn_callouts": body_xml.count('ref-type="fn"'),
        "notes": len(project.get("notes", [])),
        "refs": len(ref_rows),
        "sections": xml.count("<sec "),
        "figures": len(figure_ids(project)),
        "fig_links": xml.count('ref-type="fig"'),
        "audio": len(audio_ids(project)),
    }
    # in-text figure references must point at a <fig> that actually exists,
    # or OJS/Lens renders a dead link
    known_figs = set(figure_ids(project))
    dangling = sorted({rid for rid in re.findall(
        r'<xref ref-type="fig" rid="([^"]+)"', xml) if rid not in known_figs})
    if dangling:
        warnings.append("In-text figure reference(s) point at a figure that is not "
                        "in this article: " + ", ".join(dangling)
                        + " -- re-link them in the Body tab.")
    if stats["figures"] and not stats["fig_links"]:
        warnings.append(f"{stats['figures']} figure(s) but no in-text figure references. "
                        "Select the words that mention a figure (e.g. \"Figure 1\") and "
                        "use \"Link to figure\" so readers can click through to it in OJS.")
    if stats["fn_callouts"] != stats["notes"] and (stats["fn_callouts"] or stats["notes"]):
        warnings.append(f"{stats['fn_callouts']} footnote callout(s) in the text but "
                        f"{stats['notes']} note(s) in the back matter -- check the Notes tab.")
    low_conf = sum(1 for r in ref_rows if r["confidence"] < 2)
    if low_conf:
        warnings.append(f"{low_conf} reference(s) were only partly recognized "
                        f"(missing year/title/author) -- check them in the References tab.")
    return xml, warnings, stats, ref_rows


def _count_unlinked(project):
    from bcs_editor import _citable_holders
    n = 0
    for holder, key in _citable_holders(project):
        n += len(re.findall(r'<cite [^>]*data-status="none"', holder.get(key, "")))
    return n


def _filename_type(meta):
    """Section 'type' label for the filename, e.g. Article, Forum, Poetry."""
    subject = section_lookup(meta.get("section", ""))["subject"]
    # "ARTICLE" -> "Article", "BOOK REVIEW" -> "Book-Review",
    # "PODCASTS & NEW MEDIA" -> "Podcasts-New-Media" (no "&" in a filename)
    subject = re.sub(r"\s*&\s*", " ", subject)
    return re.sub(r"\s+", "-", subject.title()) or "Article"


def _filename_author(meta):
    """Last name of the first author, e.g. 'Chapman' from 'Kit Chapman'."""
    authors = (meta.get("authors") or "").strip()
    # first author only (authors are separated by " and ")
    first = re.split(r"\s+and\s+", authors, maxsplit=1, flags=re.I)[0].strip()
    if "," in first:            # "Last, First" style
        last = first.split(",")[0].strip()
    else:                        # "First Last" style
        parts = first.split()
        last = parts[-1] if parts else ""
    # keep letters, digits and hyphens (for hyphenated surnames); drop the rest
    last = re.sub(r"[^\w-]", "", last)
    return last or "Author"


def _printed_authors(people, byline):
    """'Given Surname, Given Surname, and Given Surname' for the copyright
    line. Falls back to the byline as typed."""
    names = [" ".join(x for x in (g, s) if x) for s, g in people]
    names = [n for n in names if n]
    if not names:
        return byline
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def issue_slug(project):
    """Bare issue number for filenames and folders, e.g. "229"."""
    meta = project.get("meta", {}) if project else {}
    issue = re.sub(r"^\s*BCS", "", (meta.get("issue_number") or "").strip(),
                   flags=re.I).strip()
    issue = re.sub(r"[^\w.-]", "-", issue).strip("-")
    return issue or "UNKNOWN"


def project_basename(project):
    """Filename stem shared by all of one article's outputs."""
    meta = project["meta"]
    return f"BCS{issue_slug(project)}-{_filename_type(meta)}-{_filename_author(meta)}"


def project_filename(project, profile=None):
    """Download filename. The lens (galley) profile keeps the plain name so
    nothing about the OJS workflow changes; the archival copy is marked."""
    base = project_basename(project)
    prof = get_profile(profile) if profile is not None else DEFAULT_PROFILE
    suffix = "" if prof.name == "lens" else f".{prof.name}"
    return f"{base}{suffix}.xml"


# ---------------------------------------------------------------------------
# DTD validation (uses the local JATS 1.4 DTD folder when available)
# ---------------------------------------------------------------------------

def find_dtd():
    here = Path(__file__).resolve().parent
    candidates = [
        here / "JATS-Publishing-1-4-MathML3-DTD" / "JATS-journalpublishing1-4-mathml3.dtd",
        here.parent / "JATS-Publishing-1-4-MathML3-DTD" / "JATS-journalpublishing1-4-mathml3.dtd",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def validate_xml(xml_string):
    """Returns (status, messages). status: 'valid' | 'invalid' | 'skipped'."""
    try:
        from lxml import etree  # type: ignore
    except ImportError:
        return "skipped", ["lxml is not installed -- run: pip install lxml"]
    try:
        parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)
        root = etree.fromstring(xml_string.encode("utf-8"), parser=parser)
    except etree.XMLSyntaxError as e:
        return "invalid", [f"Not well-formed XML: {e}"]
    dtd_path = find_dtd()
    if dtd_path is None:
        return "skipped", ["JATS 1.4 DTD folder not found next to the tool -- "
                           "well-formedness checked only."]
    try:
        dtd = etree.DTD(str(dtd_path))
    except Exception as e:
        return "skipped", [f"Could not load the DTD: {e}"]
    if dtd.validate(root):
        return "valid", []
    msgs = [str(err) for err in dtd.error_log.filter_from_errors()[:25]]  # type: ignore
    return "invalid", msgs


def transform_xml_with_xslt(xml_string, xslt_path):
    """Render JATS to HTML with the house stylesheet. The stylesheet is the
    same one the website uses, so what you preview here is what a reader
    sees."""
    from lxml import etree
    transform = etree.XSLT(etree.parse(str(xslt_path)))
    return str(transform(etree.fromstring(xml_string.encode("utf-8"))))
