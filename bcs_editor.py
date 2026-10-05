#!/usr/bin/env python3
"""
bcs_editor.py -- the article "project" model for the BC Studies JATS tool. This is the main data structure
"""

import html
import json
import math
import re
import shutil
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path

from bcs_names import split_authors

PROJECTS_DIR = Path(__file__).resolve().parent / "projects"

esc = lambda t: html.escape(t, quote=False)
esc_attr = lambda t: html.escape(t, quote=True)

# =============================================================================
# 1. TOKEN MODEL -- every inline string is parsed into flat tokens:
#    {"t": text, "i": bool, "b": bool, "sc": bool, "style_type": str,
#     "lang": str, "fn": str|None, "cite": dict|None, "fig": str|None}
#    "sc" is small caps; "style_type"/"lang" carry a <styled-content> run
#    (special-character fonts, Indigenous-language words) through the editor.
#    Tokens inside the same <cite> span share ONE cite dict (identity matters).
#    "fig" holds the id of the <fig> an in-text figure reference points at.
# =============================================================================

_ALLOWED_SKIP = {"span", "div", "p", "u", "a", "font", "s", "strike"}  # kept as text


class _TokParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []
        self._i = 0
        self._b = 0
        self._sc = 0
        self._lang = []        # stack of (style_type, xml_lang)
        self._spans = []       # what each <span> did, so </span> undoes it
        self._cite = None
        self._fn = None
        self._fig = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag in ("i", "em"):
            self._i += 1
        elif tag in ("b", "strong"):
            self._b += 1
        elif tag == "span":
            if "sc" in (a.get("class") or "").split():
                self._sc += 1
                self._spans.append("sc")
            elif a.get("data-style-type") or a.get("lang"):
                self._lang.append((a.get("data-style-type", ""), a.get("lang", "")))
                self._spans.append("lang")
            else:
                self._spans.append("")   # stray span from a paste
        elif tag == "a" and a.get("data-fig"):
            self._fig = a.get("data-fig")
        elif tag == "cite":
            self._cite = {
                "rid": a.get("data-rid", ""),
                "status": a.get("data-status", "none"),
                "basis": a.get("data-basis", ""),
            }
        elif tag == "sup":
            self._fn = a.get("data-fn", "") or None
            if self._fn is None:
                self._fn = ""  # plain sup: keep as sup without fn link
        elif tag == "br":
            self.tokens.append({"t": " ", "i": False, "b": False, "sc": False,
                                "style_type": "", "lang": "", "fn": None,
                                "cite": self._cite, "fig": self._fig})

    def handle_endtag(self, tag):
        if tag in ("i", "em"):
            self._i = max(0, self._i - 1)
        elif tag in ("b", "strong"):
            self._b = max(0, self._b - 1)
        elif tag == "span":
            what = self._spans.pop() if self._spans else ""
            if what == "lang" and self._lang:
                self._lang.pop()
            elif what == "sc" and self._sc:
                self._sc -= 1
        elif tag == "a":
            self._fig = None
        elif tag == "cite":
            self._cite = None
        elif tag == "sup":
            self._fn = None

    def handle_data(self, data):
        if data == "":
            return
        st, lg = self._lang[-1] if self._lang else ("", "")
        self.tokens.append({
            "t": data, "i": self._i > 0, "b": self._b > 0,
            "sc": self._sc > 0, "style_type": st, "lang": lg,
            "fn": self._fn, "cite": self._cite, "fig": self._fig,
        })


def html_to_tokens(html_str):
    p = _TokParser()
    p.feed(html_str or "")
    return p.tokens


def tokens_plain(tokens):
    return "".join(t["t"] for t in tokens)


def _fmt_group(tokens, mode):
    """Serialize tokens (no cite grouping) merging same-format neighbours.
    mode: 'html' (editor vocabulary) or 'jats'."""
    out, buf, buf_fmt = [], [], None
    i_tag = ("<i>", "</i>") if mode == "html" else ("<italic>", "</italic>")
    b_tag = ("<b>", "</b>") if mode == "html" else ("<bold>", "</bold>")

    def flush():
        if not buf:
            return
        text = esc("".join(buf))
        i, b, sc, st, lg = buf_fmt
        if sc:
            text = (f'<span class="sc">{text}</span>' if mode == "html"
                    else f"<sc>{text}</sc>")
        if i and b:
            text = f"{i_tag[0]}{b_tag[0]}{text}{b_tag[1]}{i_tag[1]}"
        elif i:
            text = f"{i_tag[0]}{text}{i_tag[1]}"
        elif b:
            text = f"{b_tag[0]}{text}{b_tag[1]}"
        if st or lg:
            if mode == "html":
                attrs = ((f' data-style-type="{esc_attr(st)}"' if st else "")
                         + (f' lang="{esc_attr(lg)}"' if lg else ""))
                text = f"<span{attrs}>{text}</span>"
            else:
                attrs = ((f' style-type="{esc_attr(st)}"' if st else "")
                         + (f' xml:lang="{esc_attr(lg)}"' if lg else ""))
                text = f"<styled-content{attrs}>{text}</styled-content>"
        out.append(text)

    for t in tokens:
        if t["fn"] is not None:
            flush()
            buf, buf_fmt = [], None
            label = esc(t["t"])
            if t["fn"]:  # linked footnote marker
                if mode == "html":
                    out.append(f'<sup data-fn="{esc_attr(t["fn"])}">{label}</sup>')
                else:
                    out.append(f'<xref ref-type="fn" rid="fn{esc_attr(t["fn"])}">{label}</xref>')
            else:        # plain superscript
                out.append(f"<sup>{label}</sup>")
            continue
        fmt = (t["i"], t["b"], t.get("sc", False),
               t.get("style_type", ""), t.get("lang", ""))
        if fmt != buf_fmt:
            flush()
            buf, buf_fmt = [], fmt
        buf.append(t["t"])
    flush()
    return "".join(out)


def _fig_runs(tokens):
    """Yield (fig_id_or_'', token_sublist): contiguous tokens sharing the same
    in-text figure reference target."""
    idx = 0
    while idx < len(tokens):
        f = tokens[idx].get("fig") or ""
        j = idx
        while j < len(tokens) and (tokens[j].get("fig") or "") == f:
            j += 1
        yield f, tokens[idx:j]
        idx = j


def _fmt_run(tokens, mode):
    """Serialize tokens, wrapping in-text figure references. In JATS these
    become <xref ref-type="fig" rid="fig-1">, which the HTML galley
    renders as a link that jumps to the figure."""
    out = []
    for fig, run in _fig_runs(tokens):
        inner = _fmt_group(run, mode)
        if not fig:
            out.append(inner)
        elif mode == "html":
            out.append(f'<a class="figref" data-fig="{esc_attr(fig)}">{inner}</a>')
        else:
            out.append(f'<xref ref-type="fig" rid="{esc_attr(fig)}">{inner}</xref>')
    return "".join(out)


def _cite_groups(tokens):
    """Yield (cite_dict_or_None, token_sublist) preserving order; contiguous
    tokens sharing the same cite dict (by identity) form one group."""
    idx = 0
    while idx < len(tokens):
        c = tokens[idx]["cite"]
        j = idx
        while j < len(tokens) and tokens[j]["cite"] is c:
            j += 1
        yield c, tokens[idx:j]
        idx = j


def tokens_to_editor_html(tokens):
    out = []
    for c, group in _cite_groups(tokens):
        inner = _fmt_run(group, "html")
        if c is not None:
            out.append(
                f'<cite data-rid="{esc_attr(c.get("rid", ""))}"'
                f' data-status="{esc_attr(c.get("status", "none"))}"'
                f' data-basis="{esc_attr(c.get("basis", ""))}">{inner}</cite>')
        else:
            out.append(inner)
    return "".join(out)


def tokens_to_jats(tokens):
    """Editor tokens -> JATS inline XML. Linked cites become <xref>."""
    out = []
    for c, group in _cite_groups(tokens):
        inner = _fmt_run(group, "jats")
        if c is not None and c.get("rid") and c.get("status") in ("auto", "confirmed"):
            out.append(f'<xref ref-type="bibr" rid="{esc_attr(c["rid"])}">{inner}</xref>')
        else:
            out.append(inner)
    return "".join(out)


def editor_html_to_jats(html_str):
    return tokens_to_jats(html_to_tokens(html_str))


def title_tokens(html_str):
    """The article title or subtitle -> tokens, whitespace collapsed and
    trimmed the way " ".join(s.split()) would, footnote callouts dropped.

    Both fields hold inline editor HTML, so a book or case name in a title
    can be italic. Titles saved before that were plain text, which reads
    the same way (a bare "&" parses as itself)."""
    out, prev_space = [], True
    for t in html_to_tokens(html_str):
        if t["fn"] is not None:
            continue
        text = re.sub(r"\s+", " ", t["t"])
        if prev_space:
            text = text.lstrip(" ")
        if not text:
            continue
        prev_space = text.endswith(" ")
        nt = dict(t)
        nt["t"] = text
        nt["cite"] = None
        out.append(nt)
    while out and out[-1]["t"].endswith(" "):
        out[-1]["t"] = out[-1]["t"].rstrip(" ")
        if not out[-1]["t"]:
            out.pop()
    return out


def title_plain(html_str):
    """The title's words with no markup, for lists, searches and warnings."""
    return tokens_plain(title_tokens(html_str))


def title_html(html_str):
    """The title as safe editor HTML (italics kept) for the tool's own pages."""
    return tokens_to_editor_html(title_tokens(html_str))


def _split_at(tokens, pos):
    """Split the token list so that a token boundary falls exactly at char
    offset `pos` (over the concatenated text). Returns (tokens, idx) where
    tokens[:idx] cover exactly pos chars -- or (tokens, None) if the boundary
    falls inside an atomic footnote-marker token."""
    running = 0
    for i, t in enumerate(tokens):
        nxt = running + len(t["t"])
        if nxt == pos:
            return tokens, i + 1
        if nxt > pos:
            if t["fn"] is not None:
                return tokens, None  # never split a footnote marker
            head, tail = dict(t), dict(t)
            head["t"] = t["t"][:pos - running]
            tail["t"] = t["t"][pos - running:]
            return tokens[:i] + [head, tail] + tokens[i + 1:], i + 1
        running = nxt
    return tokens, len(tokens)


def _apply_cite_spans(tokens, spans):
    """spans: list of (start_char, end_char, cite_dict). Marks the token
    ranges; returns the new token list."""
    for start, end, cite in sorted(spans, key=lambda s: s[0], reverse=True):
        tokens, i1 = _split_at(tokens, start)
        if i1 is None:
            continue
        tokens, i2 = _split_at(tokens, end)
        if i2 is None:
            continue
        for k in range(i1, i2):
            # never nest cites, and never swallow a figure reference
            if tokens[k]["cite"] is None and not tokens[k].get("fig"):
                tokens[k]["cite"] = cite
    return tokens


# =============================================================================
# 2. WORKS CITED ANALYSIS
# =============================================================================

QUOTE_CHARS = set('“”"')
YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
PAGES_RE = re.compile(r"\bpp\.\s*([A-Za-z0-9]+)\s*[–‒—-]\s*([A-Za-z0-9]+)\.?")
SINGLE_PAGE_RE = re.compile(r"\bp\.\s*([A-Za-z0-9]+)\.?")
VOL_RE = re.compile(r"\bvol\.\s*([\dIVXLC]+)\.?", re.IGNORECASE)
NO_RE = re.compile(r"\bnos?\.\s*([\d]+(?:\s*[–‒/-]\s*\d+)?)\.?", re.IGNORECASE)
DOI_RE = re.compile(r"(?:doi:\s*|https?://(?:dx\.)?doi\.org/)(10\.[^\s,;]+)", re.IGNORECASE)

# --- Chicago author-date ----------------------------------------------------
# BC Studies' social-science articles run Chicago author-date, where the year
# sits between the author and the title:
#
#     Harris, Douglas C. 2008. Landing Native Fisheries... UBC Press.
#     Boelens, Rutgerd, Jaime Hoogesteger, and Philippus Wester. 2016.
#         "Hydrosocial Territories." Water International 41, no. 1: 1-14.
#     Associated Engineering. 2019. Flood Mapping Project...
#
# That year is a better boundary than MLA's guesswork about whether the
# text before the first full stop looks like a name: it works for a corporate
# author, for six authors, and for a name longer than any length cap. Where it
# matches, it is trusted and the MLA heuristics are skipped entirely.
CHICAGO_AUTHOR_YEAR = re.compile(r"^(.{2,300}?)\.\s+(\d{4}[a-z]?)\.\s+", re.S)
CHICAGO_REPEAT_YEAR = re.compile(r"^(?:—+|-{2,3})\s*\.?\s*(\d{4}[a-z]?)\.\s+")
# "Water International 41, no. 4: 1-14" -- volume, issue and pages Chicago-style
CHICAGO_VOL_ISSUE = re.compile(r"\b(\d{1,4})\s*(?:,\s*nos?\.\s*([\d]+(?:\s*[-–/]\s*\d+)?)|\s*\((\d+)\))")
CHICAGO_PAGES = re.compile(r":\s*(\d+)\s*[-–—]\s*(\d+)")
URL_RE = re.compile(r"https?://[^\s<>\"]+")
_TRAILING_PUNCT = ".,;:)]}”’"


def _resplit_quotes(tokens):
    """Split token texts at quote characters so quote marks become their own
    tokens (needed to find the quoted article title span cleanly)."""
    out = []
    for t in tokens:
        if t["fn"] is not None:
            out.append(t)
            continue
        for piece in re.split(r'([“”"])', t["t"]):
            if piece != "":
                nt = dict(t)
                nt["t"] = piece
                out.append(nt)
    return out


_CHI_PUBLISHER = re.compile(
    r"(?:^|\.\s+)([A-Z][A-Za-z&\u2019'\- ]{2,58}?"
    r"(?:Press|Publishers?|Publishing|Books|University|UP|Institute|Society|"
    r"Foundation|House|Editions|Company|Museum|Ltd\.?|Inc\.?|Co\.))\s*[.,]")


def _chicago_publisher(text):
    """Chicago author-date names the publisher near the end and does not put a
    year after it, so the old MLA rule ("capitalised chunk, then a year") never
    fires. Match on what publishers are actually called instead."""
    m = _CHI_PUBLISHER.search(text)
    return m.group(1).strip() if m else ""


def _drop_phrase(text, phrase):
    if not phrase:
        return text
    return re.sub(re.escape(phrase), " ", text, count=1).strip()


def _span_is_italic(tokens, lo, hi):
    """Is the text between two character offsets set in italics? An entry that
    opens in italics opens with a work's title, not with an author -- which is like
    the one thing that can make the Chicago year test read a title as a name."""
    running = 0
    ital = plain = 0
    for t in tokens:
        nxt = running + len(t["t"])
        if nxt > lo and running < hi and t["fn"] is None:
            part = t["t"][max(lo - running, 0):hi - running or None]
            n = sum(1 for ch in part if ch.isalnum())
            if t["i"]:
                ital += n
            else:
                plain += n
        running = nxt
        if running >= hi:
            break
    return bool(ital) and ital > plain


def analyze_ref(html_str, prev_author_text=""):
    """Parse one Works Cited entry. Returns a dict with the (re-split) token
    list, field values, and the token spans for title/source -- everything
    build_mixed_citation() and the citation matcher need."""
    tokens = _resplit_quotes(html_to_tokens(html_str))
    plain = tokens_plain(tokens)
    stripped = plain.strip()
    lead_ws = len(plain) - len(plain.lstrip())
    is_repeat = stripped.startswith(("—", "--", "---"))

    a = {
        "tokens": tokens, "plain": plain,
        "people": [], "person_group_type": "author", "etal": False,
        "author_text": "", "resolved_author_text": prev_author_text,
        "body_start_tok": 0, "title_lo": None, "title_hi": None,
        "source_lo": None, "source_hi": None,
        "year": "", "volume": "", "issue": "", "fpage": "", "lpage": "",
        "publisher": "", "doi": "", "urls": [], "comment": "", "ptype": "other",
        "collab": "",
    }

    # --- author segment -------------------------------------------------------
    author_text = ""
    body_start_char = 0
    chicago_year = ""

    # Chicago author-date first: if the entry states its year where Chicago
    # puts it, everything before that year is the author and there is nothing to guess
    m_chi = CHICAGO_REPEAT_YEAR.match(stripped) if is_repeat else None
    if m_chi:
        author_text = prev_author_text
        chicago_year = m_chi.group(1)
        body_start_char = m_chi.end()
    elif not is_repeat:
        m_chi = CHICAGO_AUTHOR_YEAR.match(stripped)
        if m_chi and not any(q in m_chi.group(1) for q in QUOTE_CHARS) \
                and not _span_is_italic(tokens, lead_ws,
                                        lead_ws + len(m_chi.group(1))):
            author_text = m_chi.group(1).strip()
            chicago_year = m_chi.group(2)
            body_start_char = m_chi.end()

    if chicago_year:
        pass
    elif is_repeat:
        author_text = prev_author_text
        m = re.match(r"^(—+|-{2,3})\s*\.?\s*", stripped)
        body_start_char = m.end() if m else 0
    else:
        m = re.match(r"^(.*?)\.\s+", stripped)
        if m:
            candidate = m.group(1)
            c_lo, c_hi = lead_ws, lead_ws + len(candidate)
            running = 0
            alpha = []          # (token, in-candidate slice) pairs
            for t in tokens:
                nxt = running + len(t["t"])
                if nxt > c_lo and running < c_hi and t["fn"] is None:
                    part = t["t"][max(c_lo - running, 0):c_hi - running or None]
                    if any(ch.isalnum() for ch in part):
                        alpha.append((t, part))
                running = nxt
                if running >= c_hi:
                    break
            ital_chars = sum(len(part) for t, part in alpha if t["i"])
            all_chars = sum(len(part) for t, part in alpha)
            span_italic = bool(alpha) and (
                all(t["i"] for t, _part in alpha)
                or (all_chars and ital_chars / all_chars > 0.5))
            looks_like_name = ("," in candidate or len(candidate.split()) == 1) \
                and not re.search(r",\s*by\s+", candidate, re.IGNORECASE)
            if (len(candidate) <= 80 and not span_italic and looks_like_name
                    and not any(q in candidate for q in QUOTE_CHARS)):
                author_text = candidate
                body_start_char = m.end()
            elif (len(candidate) <= 80 and not span_italic
                    and not any(q in candidate for q in QUOTE_CHARS)
                    and len(candidate.split()) >= 2
                    and not re.search(r",\s*by\s+", candidate, re.IGNORECASE)
                    and re.match(r"[A-Z“‘]", stripped[m.end():] or "")
                    and candidate[:1].isupper()
                    and stripped[m.end():].lstrip()[:1] in QUOTE_CHARS):
                a["collab"] = candidate
                body_start_char = m.end()

    if body_start_char:
        tokens, idx = _split_at(tokens, body_start_char + lead_ws)
        a["tokens"] = tokens
        a["body_start_tok"] = idx if idx is not None else 0

    _ROLE_RE = re.compile(r",?\s*\b(eds?|editors?|translators?|trans)\b\.?\s*$",
                          re.IGNORECASE)

    if chicago_year and author_text and not is_repeat \
            and "," not in author_text and " and " not in author_text \
            and not re.search(r"\bet\s+al\b", author_text, re.I):
        a["collab"] = author_text
        a["author_text"] = author_text
        a["resolved_author_text"] = author_text
    elif author_text and not is_repeat:
        at = author_text
        m_role = _ROLE_RE.search(at)
        if m_role:
            role = m_role.group(1).lower()
            a["person_group_type"] = "translator" if role.startswith("tran") else "editor"
            at = at[:m_role.start()]
        m_etal = re.search(r",?\s*et\s+al\.?\s*$", at, re.IGNORECASE)
        if m_etal:
            a["etal"] = True
            at = at[:m_etal.start()]
        a["people"] = split_authors(at)
        a["author_text"] = author_text
        a["resolved_author_text"] = author_text
    elif is_repeat and prev_author_text:
        at = prev_author_text
        m_role = _ROLE_RE.search(at)
        if m_role:
            at = at[:m_role.start()]
        m_etal = re.search(r",?\s*et\s+al\.?\s*$", at, re.IGNORECASE)
        if m_etal:
            a["etal"] = True
            at = at[:m_etal.start()]
        a["people"] = split_authors(at)

    tokens = a["tokens"]

    # --- quoted article/chapter title ----------------------------------------

    qpos = [i for i in range(a["body_start_tok"], len(tokens)) if tokens[i]["t"] in QUOTE_CHARS]
    first_ital = next((i for i in range(a["body_start_tok"], len(tokens))
                       if tokens[i]["i"] and tokens[i]["t"].strip()), None)
    if len(qpos) >= 2 and (first_ital is None or qpos[0] < first_ital):
        a["title_lo"], a["title_hi"] = qpos[0] + 1, qpos[1]

    # --- italic source/container ----------------------------------------------

    start = (a["title_hi"] + 1) if a["title_hi"] is not None else a["body_start_tok"]
    i = start
    while i < len(tokens):
        if tokens[i]["i"] and tokens[i]["t"].strip():
            lo = i
            while i < len(tokens) and tokens[i]["i"]:
                i += 1
            hi = i
            before = "".join(t["t"] for t in tokens[start:lo])
            after = "".join(t["t"] for t in tokens[hi:])
            if re.search(r"review\s+of\s*$", before, re.IGNORECASE):
                continue          # reviewed work, keep scanning for the venue
            if re.match(r"\s*,?\s*special\s+issue\s+of\s+", after,
                        re.IGNORECASE):
                continue          # special-issue title; the journal follows
            a["source_lo"], a["source_hi"] = lo, hi
            break
        i += 1

    # Title-first entry (no author, no quotes, no italics): text up to the
    # first ". " is the work's own title.
    if not author_text and a["title_lo"] is None and a["source_lo"] is None:
        m_fb = re.match(r"^(.{3,120}?)\.\s+", stripped)
        if m_fb:
            m_by = re.search(r",\s*by\s+(.+)$", m_fb.group(1), re.IGNORECASE)
            if m_by:
                a["people"] = split_authors(m_by.group(1))

    # --- remainder fields ------------------------------------------------------
    consumed_tok = set(range(0, a["body_start_tok"]))
    if a["title_lo"] is not None:
        consumed_tok.update(range(a["title_lo"] - 1, a["title_hi"] + 1))
    if a["source_lo"] is not None:
        consumed_tok.update(range(a["source_lo"], a["source_hi"]))
    remainder = "".join(t["t"] for i, t in enumerate(tokens)
                        if i not in consumed_tok and t["fn"] is None)

    def take(regex, s, count=1):
        m = regex.search(s)
        return m, regex.sub(" ", s, count=count)

    m, remainder = take(DOI_RE, remainder, count=0)
    if m:
        a["doi"] = m.group(1).rstrip(".,;")
    for m in URL_RE.finditer(remainder):
        url = m.group(0)
        while url and url[-1] in _TRAILING_PUNCT:
            url = url[:-1]
        # a "URL" whose host is a DOI prefix (https://10.14288/x) is a
        # mistyped DOI -- file it as the DOI and not as a dead link
        dm = re.match(r"https?://(10\.\d{4,9}/\S+)$", url)
        if dm:
            if not a["doi"]:
                a["doi"] = dm.group(1).rstrip(".,;")
            continue
        a["urls"].append(url)
    remainder = URL_RE.sub(" ", remainder)
    m, remainder = take(PAGES_RE, remainder)
    if m:
        a["fpage"], a["lpage"] = m.group(1), m.group(2)
    else:
        m, remainder = take(SINGLE_PAGE_RE, remainder)
        if m:
            a["fpage"] = m.group(1)
    m, remainder = take(VOL_RE, remainder)
    if m:
        a["volume"] = m.group(1)
    m, remainder = take(NO_RE, remainder)
    if m:
        a["issue"] = " ".join(m.group(1).split())

    # publisher: capitalized, digit-free chunk right before the year
    # NB the leading \s* on the ^ alternative: after the italic <source> tokens
    # are removed the remainder often starts with whitespace ("  Duke UP, 2021"),
    # which used to fail the anchor and dump the publisher into <comment>.
    m_pub = re.search(r"(?:^\s*|[.,;]\s*)([A-Z][A-Za-z&'’./\- ]{2,60}?),\s*(?=(?:1[5-9]\d{2}|20\d{2})\b)",
                      remainder)
    if m_pub and not re.match(r"(?:vol|nos?|pp?|eds?|edited|translated)\b",
                              m_pub.group(1), re.IGNORECASE):
        a["publisher"] = m_pub.group(1).strip()
        remainder = remainder[:m_pub.start(1)] + " " + remainder[m_pub.end(1):]

    m, remainder = take(YEAR_RE, remainder)
    if m:
        a["year"] = m.group(1)

    # --- Chicago fix-ups -------------------------------------------------------
    if chicago_year:
        # The year Chicago prints after the author is the year of publication whatever other four-digit numbers the entry happens to contain.
        a["year"] = chicago_year
        # "Water International 41, no. 1: 1-14" and "Water International 41 (1)"
        after_source = "".join(t["t"] for i, t in enumerate(tokens)
                               if a["source_hi"] is not None and i >= a["source_hi"]
                               and t["fn"] is None)
        scope = after_source or remainder
        if not a["volume"]:
            mv = CHICAGO_VOL_ISSUE.search(scope)
            if mv:
                a["volume"] = mv.group(1)
                if not a["issue"]:
                    a["issue"] = (mv.group(2) or mv.group(3) or "").strip()
        if not a["fpage"]:
            mp = CHICAGO_PAGES.search(scope)
            if mp:
                a["fpage"], a["lpage"] = mp.group(1), mp.group(2)
        if not a["publisher"]:
            a["publisher"] = _chicago_publisher(stripped)
        if a["publisher"] and not (a["volume"] or a["issue"]):
            a["ptype"] = "chapter" if a["title_lo"] is not None and \
                re.search(r"\bIn\b", stripped) else \
                ("book" if a["title_lo"] is None else a["ptype"])

    # whatever is left over goes in the element-citation's <comment>
    leftover = re.sub(r"\s+", " ", remainder)
    leftover = re.sub(r"([.,;:])(\s*[.,;:])+", r"\1", leftover)
    leftover = leftover.strip(" .,;:()[]–—-")
    a["comment"] = leftover if re.search(r"[A-Za-z]{2}", leftover) else ""

    if chicago_year and a["comment"]:
        # Anything already filed as a field should not also be narrated in the
        # comment. Chicago repeats the publisher and the page range in places
        # the MLA remainder pass never reaches.
        for value in (a["publisher"], a["volume"], a["issue"],
                      a["fpage"], a["lpage"]):
            a["comment"] = _drop_phrase(a["comment"], value)
        a["comment"] = re.sub(r"\s{2,}", " ", a["comment"]).strip(" .,;:()[]–—-")
        if not re.search(r"[A-Za-z]{2}", a["comment"]):
            a["comment"] = ""

    has_title = a["title_lo"] is not None
    has_source = a["source_lo"] is not None
    # "quoted title + italic container + page numbers" describes a chapter in a
    # book AND an article in a newspaper. Only the book has a publisher or an
    # "edited by" line, so require one of those before calling it a chapter --
    # otherwise every newspaper piece was typed chapter, and JATS Parser's
    # Back/Chapter.php rendered it as "In: <newspaper>" with the container as
    # the work, while aggregators got the wrong document type.
    container_is_book = bool(a["publisher"]) or bool(
        re.search(r"\b(?:edited\s+by|editors?|eds?\.)\b", stripped, re.IGNORECASE))
    if a["volume"] or a["issue"]:
        a["ptype"] = "journal"
    elif has_title and has_source:
        if a["fpage"] and container_is_book:
            a["ptype"] = "chapter"
        elif (a["urls"] or a["doi"]) and not a["fpage"]:
            a["ptype"] = "webpage"
        else:
            a["ptype"] = "journal"
    elif has_source:
        a["ptype"] = "book"
    else:
        a["ptype"] = "webpage" if (a["urls"] or a["doi"]) else "other"
    return a


# =============================================================================
# 3. CITATION DETECTION -- find parenthetical citations in body/notes HTML,
#    guess their Works Cited entry, and wrap them in <cite> spans.
# =============================================================================

CAP_WORD_RE = re.compile(r"[A-Z][\w’'‐-]*")
WORD_RE = re.compile(r"[\w’'‐-]+")
PAREN_RE = re.compile(r"\(([^()\n]{1,200}?)\)")
PAGES_ONLY_RE = re.compile(
    r"^(?:(?:see|also|cf\.?)\s+)?(?:pp?\.\s*)?\d{1,4}(?:\s*[–—-]\s*\d{1,4})?"
    r"(?:\s*[,;]\s*\d{1,4}(?:\s*[–—-]\s*\d{1,4})?)*$", re.IGNORECASE)
YEAR_ONLY_RE = re.compile(r"^\d{4}$")
YEAR_RANGE_RE = re.compile(r"^\d{4}\s*[–—-]\s*\d{0,4}$")  # life dates "(1939–)"
# a number carrying a thousands separator is a quantity, not a page: MLA never
# writes "(70,614–87,504)". Catches statistics quoted mid-sentence.
THOUSANDS_RE = re.compile(r"\d,\d{3}\b")
QUOTED_RE = re.compile(r'[“"]([^”"]{2,120})[”"]')
# a citation that points the reader elsewhere rather than continuing the
# argument -- still a citation, but weak evidence about what the passage is
# about, so it gets a reduced say in the running context
_ASIDE_RE = re.compile(
    r"^(?:see\s+also|see|cf\.?|compare|e\.?g\.?|but\s+see|qtd\.?\s+in)\b",
    re.IGNORECASE)

# normalization used for title matching: curly quotes/dashes -> plain, drop
# punctuation, collapse case & whitespace, so "Turtle’s" == "Turtles" etc.
_NORM_TRANS = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                             "–": "-", "—": "-", "‒": "-"})


def _norm(s):
    s = (s or "").translate(_NORM_TRANS).lower()
    s = re.sub(r"[^\w\s-]", " ", s.replace("'", ""))
    return " ".join(s.split())


# words that start a citation segment but are never a short title
_NOT_TITLE_WORDS = {"see", "also", "cf", "qtd", "in", "ibid", "vol", "ch",
                    "chapter", "emphasis", "italics", "original", "added",
                    "translation", "trans", "sic", "ellipsis", "mine"}


def _title_hits(cand, ref_info, fields, restrict=None, prefix_only=False):
    """Rids whose given field(s) match a short-title candidate. Exact
    matches beat prefix matches ("Diaspora" -> the entry titled exactly
    "Diaspora", not "Diaspora and Nation in..."), which beat plain
    containment (short titles are the opening words of the full
    title); restrict, when given, limits the search to those rids.
    prefix_only drops the containment tier, for callers that cannot afford
    its false positives."""
    cand = _norm(cand)
    if len(cand) < 3:
        return []
    exact, starts, contains = [], [], []
    for rid, info in ref_info.items():
        if restrict is not None and rid not in restrict:
            continue
        for f in fields:
            v = info.get(f) or ""
            if not v:
                continue
            if v == cand:
                exact.append(rid)
                break
            if v.startswith(cand):
                starts.append(rid)
                break
            if not prefix_only and len(cand) >= 4 and cand in v:
                contains.append(rid)
                break
    return exact or starts or contains


# =============================================================================
# 3. CITATION CONTEXT (the salience model)
# =============================================================================
#
# Two kinds of citation can only be resolved from the surrounding text:
# page-only ones -- "(26)" -- and repeat citations of an author who has
# several entries in the Works Cited.
#
# The model is a mini "salience stack". Every time a work is named in the
# narrative -- by author surname, by quoted article title, or by italic book
# title -- the stack records WHERE it was named and HOW MUCH weight that
# mention carried. Salience is then
#
#     salience = recency + a small floor earned by frequency
#
# The two terms do different jobs, and keeping them ADDITIVE is the whole
# trick. Recency wins outright whenever anything has been named nearby: MLA's
# convention is that a bare "(48)" belongs to whoever was just named, and no
# amount of earlier discussion should outvote the sentence the citation is
# sitting in. But recency decays fast, and once nothing has been named for a
# sentence or two the frequency floor is all that is left standing -- so the
# work the section keeps returning to picks up the citation instead of some
# critic mentioned once, three paragraphs ago. That second case is what the
# old "last work named wins" rule got wrong.
#
# Distance is measured in CHARACTERS of narrative text two
# names in the same sentence are genuinely close together, two names a paragraph apart are not

_HALF_LIFE = 220.0      # characters of narrative after which recency halves
                        # (~40 words, i.e. about a sentence)
_BLOCK_GAP = 60         # extra distance charged at a paragraph boundary
_SECTION_GAP = 400      # ...and at a section heading, which resets the topic
_FREQ_FLOOR = 0.16      # the most that sheer frequency can be worth. Below
                        # the recency of anything named in the same sentence,
                        # above the recency of anything a paragraph back.
_FLOOR_HALF_LIFE = 2000.0
                        # ...and the floor fades too, just far more slowly
                        # (~a page of text). Without this, one heavily
                        # discussed work stays the fallback for the whole
                        # article and page-only citations to something that
                        # was never in the Works Cited get linked to it
                        # instead of being flagged.
_MASS_CAP = 12.0        # stops a much-discussed author becoming permanent
_ASIDE_LAG = 300        # "(see Razack)", "(cf. Mutua)": a pointer away from
                        # the argument, credited as if named this far back so
                        # it can't capture the next "(27)"
_HEADING_BOOST = 2.0    # a name in a heading counts as ~2 mentions
_TITLE_BONUS = 1.25     # naming the work beats naming only its author
_CITATION_WEIGHT = 1.15 # an actually-resolved citation is strong evidence
_MIN_SALIENCE = 0.10    # below this, context is too stale to guess from
_MIN_MARGIN = 1.15      # For a bare "(48)" the candidates are different
                        # AUTHORS, and a wrong link there is an error in
                        # published XML, so a close call is left unlinked for
                        # the review screen to catch.
_SAME_AUTHOR_MARGIN = 1.02
                        # But when the segment already names the author and we
                        # are only choosing between that author's own works,
                        # a close call is exactly what the frequency term is
                        # for -- and the fallback is no link at all, so it is
                        # worth taking the leader and flagging it.
_STACK_MAX = 24         # keep the stack small; the tail is never consulted


def _surname_key(word):
    """Lookup key for a possible in-text surname: strip possessives and
    trailing punctuation ("Minogue’s" -> "minogue")."""
    return re.sub(r"(?:[’']s|[.,’'?!])+$", "", word).lower()


def new_context():
    """A fresh, empty citation context. "clock" is a running character
    position through the article."""
    return {"stack": {}, "clock": 0}


def _advance(ctx, gap):
    """Charge `gap` characters of distance without any text -- what a
    paragraph break or a section heading is worth as a fade."""
    ctx["clock"] = ctx.get("clock", 0) + gap
    _prune(ctx)


def _salience(ctx, entry):
    """recency (clause scale) + topic prior (page scale), as described above."""
    age = max(0, ctx.get("clock", 0) - entry["last"])
    recency = 0.5 ** (age / _HALF_LIFE)
    floor = (_FREQ_FLOOR * math.log1p(entry["mass"]) / math.log1p(_MASS_CAP)
             * 0.5 ** (age / _FLOOR_HALF_LIFE))
    return recency + floor


def _prune(ctx):
    """Drop entries that have faded past usefulness, and cap the stack."""
    stack = ctx.get("stack") or {}
    for rid in list(stack):
        if _salience(ctx, stack[rid]) < 0.01:
            del stack[rid]
    if len(stack) > _STACK_MAX:
        ranked = sorted(stack, key=lambda r: _salience(ctx, stack[r]))
        for rid in ranked[:len(stack) - _STACK_MAX]:
            del stack[rid]


def _add_to_stack(ctx, rid, weight=1.0, source="narrative", lag=0):
    """Credit one mention of `rid` at the current clock position. `mass` is
    the accumulated weight of every mention (frequency); `last` is where it
    was most recently named (recency). `lag` backdates the mention, which is
    how an aside earns its keep in the frequency term without claiming to be
    the thing under discussion right now."""
    if not rid or weight <= 0:
        return
    stack = ctx.setdefault("stack", {})
    e = stack.setdefault(rid, {"mass": 0.0, "count": 0, "last": -10 ** 6,
                               "source": source})
    e["mass"] = min(_MASS_CAP, e["mass"] + weight)
    e["count"] += 1
    e["last"] = max(e["last"], ctx.get("clock", 0) - lag)
    e["source"] = source


def _mention(ctx, rid_weights, source="narrative", lag=0):
    """Record one mention event at the current position. The clock is NOT
    moved here -- it tracks characters of text, and the caller advances it as
    it walks the article -- so several entities named in one breath (a shared
    surname, say) are all equally recent, as they should be."""
    if not rid_weights:
        return
    for rid, weight in rid_weights:
        _add_to_stack(ctx, rid, weight, source, lag)
    _prune(ctx)


def _rank_stack(ctx, restrict=None):
    """(rid, salience) for the live context, best first, ties going to
    whichever was mentioned most recently."""
    stack = ctx.get("stack") or {}
    items = [(rid, e) for rid, e in stack.items()
             if restrict is None or rid in restrict]
    items.sort(key=lambda kv: (_salience(ctx, kv[1]), kv[1]["last"]),
               reverse=True)
    return [(rid, _salience(ctx, e)) for rid, e in items]


def _in_this_sentence(ctx, restrict=None):
    """The work named in the same sentence as the citation being resolved, or
    "". This outranks the stack outright: "Zakaria argues that ... (60)" is
    about Zakaria however much the section has been discussing someone else.
    When a sentence names more than one work the later one is taken, which is
    usually the one the quotation is hanging off."""
    for rid in reversed(ctx.get("sentence") or []):
        if restrict is None or rid in restrict:
            return rid
    return ""


def _best_from_stack(ctx, restrict=None, min_score=_MIN_SALIENCE, margin=None):
    """The work the surrounding text is most plausibly about, or "" when
    nothing is salient enough, or when the top two are too close to call.
    Returning "" leaves the citation flagged for a human instead of linking it
    to a coin-flip winner.

    With `margin` left as None the threshold is chosen from the candidates:
    strict when the run-off is between different authors (getting that wrong
    puts an error in the XML), permissive when it is between one
    author's own works (nobody is misattributed, and the alternative is no
    link at all)."""
    ranked = _rank_stack(ctx, restrict)
    if not ranked:
        return ""
    rid, score = ranked[0]
    if score < min_score:
        return ""
    if len(ranked) > 1 and ranked[1][1] > 0:
        if margin is None:
            by = ctx.get("author_of") or {}
            first, second = by.get(rid), by.get(ranked[1][0])
            margin = (_SAME_AUTHOR_MARGIN if first and first == second
                      else _MIN_MARGIN)
        if score < ranked[1][1] * margin:
            return ""
    return rid


# Sentence boundaries. The lookbehind keeps spaced ellipses -- "the margin . . .
# shapes it", which MLA uses constantly inside quotations -- from splitting the
# sentence and hiding the author named at the start of it. The lookahead wants
# a plausible sentence opener. Abbreviations ("vol.", "Dr.") still produce the
# odd false split, which only shortens the window we look back over, so it
# costs a missed hint rather than a wrong one.
_SENT_END_RE = re.compile(
    r"(?<=[^\s.])[.!?]+[”’\"')\]]?\s+(?=[“”‘’\"'(\[]?[A-Z0-9])")


def _sentence_start(plain, upto):
    """Char offset of the start of the sentence containing `upto`."""
    start = 0
    for m in _SENT_END_RE.finditer(plain, 0, max(0, upto)):
        start = m.end()
    return start


def _italic_runs(tokens):
    """(char_offset, text) for every contiguous run of italic tokens -- in
    MLA, an italic run in the narrative is a book/journal title."""
    out, pos, start, buf = [], 0, None, []
    for t in tokens:
        if t.get("i"):
            if start is None:
                start = pos
            buf.append(t["t"])
        elif buf:
            out.append((start, "".join(buf).strip()))
            start, buf = None, []
        pos += len(t["t"])
    if buf:
        out.append((start, "".join(buf).strip()))
    return [(s, txt) for s, txt in out if txt]


def _context_events(tokens, surname_map, ref_info, lower_keys):
    """Every mention of a Works Cited entry in this run of tokens, as
    (char_offset, rids, kind) with kind in {"name", "title"}, in reading
    order. All three passes report CHARACTER offsets so they interleave
    correctly."""
    plain = tokens_plain(tokens)
    events = []

    # 1. author surnames ("Pinder argues...")
    for m in WORD_RE.finditer(plain):
        w = m.group(0)
        key = _surname_key(w)
        # lowercase words are surnames only if the Works Cited styles them
        # that way ("bissett")
        if not w[:1].isupper() and key not in lower_keys:
            continue
        rids = surname_map.get(key)
        if rids:
            events.append((m.start(), set(rids), "name"))

    # 2. quoted short titles (“Trusted Vagueness”)
    for m in QUOTED_RE.finditer(plain):
        q = m.group(1)
        if len(q) >= 4:
            hits = _title_hits(q, ref_info, ("title_norm", "plain_norm"))
            if len(hits) == 1:
                events.append((m.start(), {hits[0]}, "title"))

    # 3. italic container titles (Dancing in the Dark)
    for start, run_text in _italic_runs(tokens):
        if len(run_text) < 4:
            continue
        hits = (_title_hits(run_text, ref_info, ("source_norm",))
                or _title_hits(run_text, ref_info, ("body_norm", "plain_norm")))
        if len(hits) == 1:
            events.append((start, {hits[0]}, "title"))

    events.sort(key=lambda e: e[0])
    return events


def _update_context(ctx, tokens, surname_map, ref_info, lower_keys, boost=1.0):
    """Feed a run of narrative text into the salience stack, in reading order,
    and leave the clock standing at the end of that run. `tokens` -- not HTML
    -- so italic titles survive.

    Each mention is recorded at ITS OWN character position inside the run, so
    "as Rothberg argues ... (48)" beats a name from the start of the same
    paragraph."""
    if not tokens:
        return
    base = ctx.get("clock", 0)
    plain_len = sum(len(t["t"]) for t in tokens)
    for pos, rids, kind in _context_events(tokens, surname_map, ref_info,
                                           lower_keys):
        ctx["clock"] = base + pos
        weight = boost * (_TITLE_BONUS if kind == "title" else 1.0)
        if len(rids) == 1:
            _mention(ctx, [(next(iter(rids)), weight)], kind)
        elif len(rids) <= 4:
            # "Atwood" when Atwood has three entries: we can't tell which work
            # is meant, but Atwood's works as a group become more salient than
            # an unrelated author, which is enough to settle a later "(26)".
            share = weight / (len(rids) + 1.0)
            _mention(ctx, [(rid, share) for rid in rids], "name-shared")
    ctx["clock"] = base + plain_len


def _update_context_html(ctx, html_str, surname_map, ref_info, lower_keys,
                         boost=1.0):
    """_update_context for a stored HTML string (headings, epigraph sources)."""
    if html_str:
        _update_context(ctx, html_to_tokens(html_str), surname_map, ref_info,
                        lower_keys, boost)


def next_ref_id(project):
    mx = 0
    for g in project.get("ref_groups", []):
        for r in g["refs"]:
            m = re.match(r"cit(\d+)$", r.get("id") or "")
            if m:
                mx = max(mx, int(m.group(1)))
    return f"cit{mx + 1:03d}"


_COLLAB_STOPWORDS = {"the", "of", "and", "for", "department", "ministry",
                     "office", "government", "association", "council"}


def build_ref_indexes(project):
    """Assign missing ref ids; return (surname_map, ref_info, lower_keys).
    surname_map: lowercased surname -> set of rids.
    lower_keys: surname keys whose Works Cited form is lowercase-styled
    (e.g. "bissett"), so in-text matching accepts them uncapitalized.
    ref_info: rid -> {"label", "plain_lower", "people", plus normalized
    matching fields: "title_norm" (quoted article/chapter title),
    "source_norm" (italic container/book), "body_norm" (everything after the
    author segment -- catches title-first entries like "Review of novel,
    ..."), "plain_norm" (whole entry)."""
    surname_map = {}
    ref_info = {}
    lower_keys = set()
    for g in project.get("ref_groups", []):
        prev_author = ""
        for r in g["refs"]:
            if not r.get("id"):
                r["id"] = next_ref_id(project)
            a = analyze_ref(r["html"], prev_author)
            prev_author = a["resolved_author_text"]
            plain = " ".join(a["plain"].split())
            toks = a["tokens"]
            title_txt = ("".join(t["t"] for t in toks[a["title_lo"]:a["title_hi"]])
                         if a["title_lo"] is not None else "")
            source_txt = ("".join(t["t"] for t in toks[a["source_lo"]:a["source_hi"]])
                          if a["source_lo"] is not None else "")
            body_txt = "".join(t["t"] for t in toks[a["body_start_tok"]:])
            ref_info[r["id"]] = {
                "label": plain[:90],
                "plain_lower": plain.lower(),
                "people": a["people"],
                "collab": a.get("collab", ""),
                "year": a.get("year", ""),
                "title_norm": _norm(title_txt),
                "source_norm": _norm(source_txt),
                "body_norm": _norm(body_txt),
                "plain_norm": _norm(plain),
            }
            # A corporate author is cited by its name in the running text --
            # "(British Columbia 2023a)", "(Okanagan Nation Alliance 2021)" --
            # so every substantial word of it has to be findable the way a
            # surname is, or the whole government-document half of a BC Studies
            # bibliography goes unlinked.
            if a.get("collab"):
                for word in re.findall(r"[A-Za-z][\w\u2019'-]{2,}", a["collab"]):
                    if word.lower() in _COLLAB_STOPWORDS:
                        continue
                    surname_map.setdefault(word.lower(), set()).add(r["id"])
            for surname, _given in a["people"]:
                surname_map.setdefault(surname.lower(), set()).add(r["id"])
                if surname[:1].islower():
                    lower_keys.add(surname.lower())
                # multi-word surnames ("van Koeverden") are cited by their
                # last word too
                last = surname.split()[-1].lower() if surname.split() else ""
                if last and last != surname.lower():
                    surname_map.setdefault(last, set()).add(r["id"])
                    if last[:1].islower() and surname[:1].islower():
                        lower_keys.add(last)
    return surname_map, ref_info, frozenset(lower_keys)


def _quote_is_the_segment(seg_text, quoted):
    """True when the quoted matter is essentially all there is in the segment
    -- the shape of a real short-title citation ("Limits" 938) rather than a
    quotation dropped inside a parenthetical remark."""
    if not quoted:
        return False
    rest = seg_text
    for q in quoted:
        rest = rest.replace(q, "", 1)
    rest = re.sub(r"[“”\"'’‘,;:.\-–—\d\s]", "", rest)
    return len(rest) <= 12


def _segment_guess(seg_text, seg_italic_text, surname_map, ref_info, ctx,
                   lower_keys=frozenset()):
    """Decide (rid, status, basis) for one citation segment."""
    matched = set()
    seg_surnames = set()
    for w in WORD_RE.findall(seg_text):
        key = _surname_key(w)
        if not w[:1].isupper() and key not in lower_keys:
            continue  # lowercase word: only a surname if cited that way ("bissett")
        rids = surname_map.get(key)
        if rids:
            seg_surnames.add(key)
            matched.update(rids)
            if len(rids) == 1:
                return next(iter(rids)), "auto", "name"
    # Chicago author-date puts the year in the citation itself -- "(Harris
    # 2008)", "(British Columbia 2023a)" -- which settles which of an author's
    # works is meant without any appeal to context. Where the year is printed,
    # it is the strongest evidence in the segment
    if len(matched) > 1:
        years = {m.group(1) for m in re.finditer(r"\b((?:1[5-9]|20)\d{2})[a-z]?\b",
                                                 seg_text)}
        if years:
            by_year = {rid for rid in matched
                       if ref_info.get(rid, {}).get("year", "")[:4] in years}
            if len(by_year) == 1:
                return next(iter(by_year)), "auto", "name-year"
            if by_year:
                matched = by_year

    if len(seg_surnames) >= 2:
        # "(qtd. in Assaly and Chong 12)": if exactly one ref is co-authored
        # by every surname in the segment, that's the one
        co = [rid for rid in matched
              if seg_surnames <= {s.lower() for s, _g in
                                  ref_info.get(rid, {}).get("people", [])}]
        if len(co) == 1:
            return co[0], "auto", "name"
        if len(co) > 1:
            # same team, different name order ("Assaly and Chong" vs "Chong
            # and Assaly") -- match the order the surnames appear in
            seg_order = [_surname_key(w) for w in WORD_RE.findall(seg_text)
                         if _surname_key(w) in seg_surnames]
            ordered = [rid for rid in co
                       if [s.lower() for s, _g in
                           ref_info.get(rid, {}).get("people", [])
                           if s.lower() in seg_surnames] == seg_order]
            if len(ordered) == 1:
                return ordered[0], "auto", "name"
    quoted = QUOTED_RE.findall(seg_text)
    if matched:
        # verbatim duplicate Works Cited entries: any of them will do
        plains = {ref_info.get(rid, {}).get("plain_lower", rid) for rid in matched}
        if len(plains) == 1 and len(matched) > 1:
            return sorted(matched)[0], "auto", "name"
        # several works by the same author: use the rest of the segment to
        # tell them apart -- a quoted short title ("Limits" 938), an italic
        # title, or any distinguishing word ("email", "lecture")
        for q in quoted:
            hits = _title_hits(q, ref_info, ("title_norm", "plain_norm"),
                               restrict=matched)
            if len(hits) == 1:
                return hits[0], "auto", "title"
        if seg_italic_text:
            # italic = book/container title in MLA, so the italic-source
            # field alone gets first crack before broader fields
            hits = (_title_hits(seg_italic_text, ref_info, ("source_norm",),
                                restrict=matched)
                    or _title_hits(seg_italic_text, ref_info,
                                   ("body_norm", "plain_norm"), restrict=matched))
            if len(hits) == 1:
                return hits[0], "auto", "title"
        words = [w for w in re.findall(r"[a-z][a-z-]{3,}", _norm(seg_text))
                 if w not in ("qtd", "also") and w not in seg_surnames
                 and not any(w in s for s in seg_surnames)]
        if words:
            hits = [rid for rid in matched
                    if all(w in ref_info.get(rid, {}).get("plain_norm", "")
                           for w in words)]
            if len(hits) == 1:
                return hits[0], "auto", "title"
        # Nothing in the segment separates this author's works, so ask the
        # context which of THEM the passage has been discussing. Restricting
        # to `matched` is the point, the running leader may well be a
        # different author, but among this author's works there is often a clear one 
        best = (_in_this_sentence(ctx, restrict=matched)
                or _best_from_stack(ctx, restrict=matched,
                                    margin=_SAME_AUTHOR_MARGIN))
        if best:
            return best, "auto", "context"
        return "", "none", "ambiguous"        # surname shared by several refs
    # --- no surname in the segment: title-based matching -------
    # quoted short title, e.g. ("Trusted Vagueness" 33-34). The length guard
    # keeps a quotation embedded in a genuine aside -- "(echoing what I call
    # above "soft solidarity")" -- from being read as a citation to the work
    # it happens to name: a real MLA citation is the title plus a locator
    if _quote_is_the_segment(seg_text, quoted):
        for q in quoted:
            hits = _title_hits(q, ref_info, ("title_norm", "plain_norm"))
            if len(hits) == 1:
                return hits[0], "auto", "title"
    # italic short title, e.g. (Dancing 70) with "Dancing" italicized --
    # MLA italicizes book/container titles, so the italic-source field of
    # the entries is tried on its own before the broader fields
    if seg_italic_text:
        hits = (_title_hits(seg_italic_text, ref_info, ("source_norm",))
                or _title_hits(seg_italic_text, ref_info,
                               ("body_norm", "plain_norm")))
        if len(hits) == 1:
            return hits[0], "auto", "title"
    core = seg_text.strip()
    # "(82, emphasis mine)" etc.: the qualifier doesn't change the target
    core = re.sub(r"\s*[,;]\s*(?:emphasis|italics|my\s+(?:emphasis|translation)|"
                  r"trans\.|sic)[\w\s.]*$", "", core, flags=re.IGNORECASE)
    # page-only citation, e.g. "(26)" or "(26-27)": pure context work
    if PAGES_ONLY_RE.match(core) and not YEAR_ONLY_RE.match(core):
        best = _in_this_sentence(ctx) or _best_from_stack(ctx)
        if best:
            return best, "auto", "context"
        return "", "none", "unmatched"
    if (not quoted and not any(ch.isdigit() for ch in core)
            and len(core) <= 60 and 2 <= len(core.split()) <= 5
            and not core.isupper()
            and _norm(core).split(" ")[0] not in _NOT_TITLE_WORDS):
        hits = _title_hits(core, ref_info,
                           ("plain_norm", "title_norm", "source_norm"),
                           prefix_only=True)
        if len(hits) == 1:
            return hits[0], "auto", "title"
        if len(hits) > 1:
            return "", "none", "ambiguous"
    if any(ch.isdigit() for ch in core) and not quoted and not seg_italic_text:
        m_t = re.match(r"^([^\d]{4,80}?)\s+\d", core)
        if m_t:
            cand = m_t.group(1).strip(" ,.;:")
            first = _norm(cand).split(" ")[0] if _norm(cand) else ""
            if first and first not in _NOT_TITLE_WORDS:
                hits = [rid for rid, info in ref_info.items()
                        if info.get("title_norm", "").startswith(_norm(cand))
                        or info.get("body_norm", "").startswith(_norm(cand))]
                if len(hits) == 1:
                    return hits[0], "auto", "title"
    return "", "none", "unmatched"


def _tokens_in_range(tokens, start, end):
    """[(token, a, b)] for every token overlapping char range [start, end) of
    the concatenated plain text; a/b are slice offsets inside that token."""
    out, pos = [], 0
    for t in tokens:
        n = len(t["t"])
        nxt = pos + n
        if nxt > start and pos < end:
            out.append((t, max(0, start - pos), min(n, end - pos)))
        pos = nxt
        if pos >= end:
            break
    return out


def _subtokens(tokens, start, end):
    """A standalone token list for char range [start, end), formatting (and so
    italic titles) intact."""
    return [dict(t, t=t["t"][a:b])
            for t, a, b in _tokens_in_range(tokens, start, end) if b > a]


def _detect_in_tokens(tokens, surname_map, ref_info, ctx, lower_keys=frozenset(),
                      lead_in=()):
    """Wrap new citation spans in one block, updating the salience stack in
    document order so each citation is judged by what was said before it.

    `lead_in` is the works named in the sentence that introduced this block --
    non-empty only for a block quote, which grammatically continues the
    sentence before it ("As Warah writes:") and whose citation therefore
    belongs to a source named outside the block."""
    plain = tokens_plain(tokens)
    spans = []
    prev_end = 0

    def range_tokens(a, b):
        return _tokens_in_range(tokens, a, b)

    _advance(ctx, _BLOCK_GAP)   # a paragraph break puts distance on the clock

    for m in PAREN_RE.finditer(plain):
        # the narrative since the previous citation feeds the context FIRST
        _update_context(ctx, _subtokens(tokens, prev_end, m.start()),
                        surname_map, ref_info, lower_keys)
        prev_end = m.end()

        inner, inner_off = m.group(1), m.start(1)
        rtoks = range_tokens(m.start(), m.end())

        # already inside a <cite> span: leave it alone, but let it inform the
        # context -- a citation the editor confirmed is the strongest signal
        # available about what this passage is about
        existing = next((t["cite"] for t, _, _ in rtoks if t["cite"] is not None), None)
        if existing is not None:
            if existing.get("rid") and existing.get("status") in ("auto", "confirmed"):
                weight = _CITATION_WEIGHT * (
                    1.4 if existing.get("status") == "confirmed" else 1.0)
                _mention(ctx, [(existing["rid"], weight)], "citation",
                         lag=_ASIDE_LAG if _ASIDE_RE.match(inner.strip()) else 0)
            ctx["clock"] += m.end() - m.start()
            continue

        ctx["sentence"] = list(lead_in) + [
            next(iter(rids))
            for _p, rids, _k in _context_events(
                _subtokens(tokens, _sentence_start(plain, m.start()), m.start()),
                surname_map, ref_info, lower_keys)
            if len(rids) == 1]

        # several citations in one parenthesis, split on semicolons
        pos = 0
        for seg in inner.split(";"):
            seg_start = inner_off + pos
            pos += len(seg) + 1
            lead = len(seg) - len(seg.lstrip())
            core = seg.strip()
            if not core:
                continue
            s0, s1 = seg_start + lead, seg_start + lead + len(core)

            italic_text = "".join(
                t["t"][a:b] for t, a, b in range_tokens(s0, s1) if t["i"])
            has_digit = any(ch.isdigit() for ch in core)
            has_cap = bool(CAP_WORD_RE.search(core))

            # skip non-citation asides like "(emphasis added)"
            if not (has_digit or italic_text or has_cap):
                continue

            rid, status, basis = _segment_guess(
                core, italic_text, surname_map, ref_info, ctx, lower_keys)

            if YEAR_ONLY_RE.match(core) or YEAR_RANGE_RE.match(core):
                continue
            if THOUSANDS_RE.search(core):
                continue
            if not rid and basis == "unmatched" and not has_digit and not italic_text:
                continue

            if rid:
                _mention(ctx,
                         [(rid, _CITATION_WEIGHT * (0.5 if basis == "context" else 1.0))],
                         "citation",
                         lag=_ASIDE_LAG if _ASIDE_RE.match(core) else 0)

            spans.append((s0, s1, {"rid": rid, "status": status, "basis": basis}))

        ctx["clock"] += m.end() - m.start()   # the citation's own text
        ctx["sentence"] = []

    # trailing narrative after the last citation still sets up the next block
    _update_context(ctx, _subtokens(tokens, prev_end, len(plain)),
                    surname_map, ref_info, lower_keys)

    return _apply_cite_spans(tokens, spans)


CITABLE_KINDS = {"p", "blockquote", "epigraph"}
# not citable themselves, but they name the works a section is about
CONTEXT_KINDS = {"heading", "epigraph-source", "fig-caption"}
# blocks that continue the sentence introducing them ("As Warah writes:")
QUOTING_KINDS = {"blockquote", "epigraph"}


def _final_sentence_rids(tokens, surname_map, ref_info, lower_keys):
    """The works named in the last sentence of a block -- the lead-in a
    following block quote hangs off."""
    plain = tokens_plain(tokens)
    tail = _subtokens(tokens, _sentence_start(plain.rstrip(),
                                              len(plain.rstrip())), len(plain))
    return tuple(next(iter(rids))
                 for _p, rids, _k in _context_events(tail, surname_map,
                                                     ref_info, lower_keys)
                 if len(rids) == 1)


def _citable_holders(project):
    """Yield (holder_dict, key) for every inline string that may contain
    citations, in reading order."""
    for holder, key, role in _walk_holders(project):
        if role == "cite":
            yield holder, key


def _walk_holders(project):
    """Yield (holder_dict, key, role) in reading order. role "cite" may
    contain citations; role "context" only feeds the salience stack."""
    for b in project.get("blocks", []):
        kind = b.get("kind")
        if kind in CITABLE_KINDS:
            yield b, "html", "cite"
        elif kind in CONTEXT_KINDS:
            yield b, "html", "context"
    for n in project.get("notes", []):
        for part in n.get("parts", []):
            yield part, "html", "cite"


def refresh_citations(project):
    """(Re-)run citation detection. Existing <cite> spans are always kept."""
    if not any(g["refs"] for g in project.get("ref_groups", [])):
        return project
    surname_map, ref_info, lower_keys = build_ref_indexes(project)

    ctx = new_context()
    # who wrote what, so a run-off between two works can tell whether it is
    # choosing between authors or between one author's works
    ctx["author_of"] = {
        rid: frozenset(s.lower() for s, _g in info.get("people", []))
        for rid, info in ref_info.items()}
    lead_in = ()
    for holder, key, role in _walk_holders(project):
        if role == "context":
            # A heading is a topic change: fade what came before, then let the
            # heading's own names land hard. Doing this in READING ORDER is
            # what makes it useful -- a section's topic is only salient while
            # that section is being processed.
            if holder.get("kind") == "heading":
                _advance(ctx, _SECTION_GAP)
            _update_context_html(ctx, holder.get(key, ""), surname_map,
                                 ref_info, lower_keys,
                                 boost=_HEADING_BOOST
                                 if holder.get("kind") == "heading" else 1.0)
            lead_in = ()
            continue
        tokens = html_to_tokens(holder.get(key, ""))
        quoting = holder.get("kind") in QUOTING_KINDS
        tokens = _detect_in_tokens(tokens, surname_map, ref_info, ctx,
                                   lower_keys,
                                   lead_in=lead_in if quoting else ())
        holder[key] = tokens_to_editor_html(tokens)
        # remember who this block's closing sentence named, in case the next
        # block is the quotation it was introducing
        lead_in = () if quoting else _final_sentence_rids(
            tokens, surname_map, ref_info, lower_keys)

    return project


# =============================================================================
# 4. PARSED PIECE -> PROJECT (import path)
# =============================================================================

def _styled_to_span(m):
    attrs = m.group(1)
    st = re.search(r'style-type="([^"]*)"', attrs)
    lg = re.search(r'xml:lang="([^"]*)"', attrs)
    out = ""
    if st:
        out += f' data-style-type="{st.group(1)}"'
    if lg:
        out += f' lang="{lg.group(1)}"'
    return f"<span{out}>"


def jats_inline_to_editor(s):
    s = re.sub(r'<ext-link[^>]*xlink:href="([^"]*)"[^>]*>', r'<a href="\1">', s or "")
    s = s.replace("</ext-link>", "</a>")
    s = s.replace("<italic>", "<i>").replace("</italic>", "</i>")
    s = s.replace("<bold>", "<b>").replace("</bold>", "</b>")
    s = s.replace("<sc>", '<span class="sc">').replace("</sc>", "</span>")
    s = re.sub(r'<styled-content([^>]*)>', _styled_to_span, s)
    s = s.replace("</styled-content>", "</span>")
    s = re.sub(r'<xref ref-type="fn" rid="fn([^"]*)">(.*?)</xref>',
               r'<sup data-fn="\1">\2</sup>', s)
    return s


# -- tables -------------------------------------------------------------------
# A table block is
#   {"kind": "table", "id": "tbl-1", "label": "Table 1", "html": <caption>,
#    "header_rows": 1, "foot_html": <notes under the table>,
#    "rows": [[{"html": .., "th": bool, "colspan": n, "rowspan": n}, ..], ..]}
# with every string in the editor's inline HTML. The caption lives in "html",
# as a figure's does, so the editor's text box and toolbar work on it
# unchanged. Drafts made before this carried the table as a finished JATS
# string in "html" and the caption in "caption"; upgrade_tables() converts
# them when they are opened.

def table_block(t):
    """A table as bcs_idml gathers it (inline JATS) -> a table block."""
    rows = [[{"html": jats_inline_to_editor(c.get("html", "")),
              "th": bool(c.get("th")),
              "colspan": int(c.get("colspan") or 1),
              "rowspan": int(c.get("rowspan") or 1)} for c in row]
            for row in t.get("rows", [])]
    return {"kind": "table", "level": 1, "id": "",
            "label": t.get("label", ""),
            "html": jats_inline_to_editor(t.get("caption", "")),
            "header_rows": int(t.get("header_rows") or 0),
            "rows": [r for r in rows if r],
            "foot_html": _join_paras(t.get("foot") or [])}


def table_block_from_jats(xml):
    """A JATS <table> string -> a table block (for older drafts)."""
    from lxml import etree  # type: ignore
    rows, header_rows = [], 0
    try:
        root = etree.fromstring(
            f'<w xmlns:xlink="http://www.w3.org/1999/xlink">{xml}</w>')
    except etree.XMLSyntaxError:
        root = None
    if root is not None:
        for tr in root.iter("tr"):
            cells = []
            for c in tr:
                if c.tag not in ("td", "th"):
                    continue
                inner = (c.text and _esc_text(c.text) or "") + "".join(
                    etree.tostring(k, encoding="unicode") for k in c)
                inner = inner.replace(
                    ' xmlns:xlink="http://www.w3.org/1999/xlink"', "")
                cells.append({"html": jats_inline_to_editor(inner.strip()),
                              "th": c.tag == "th",
                              "colspan": int(c.get("colspan") or 1),
                              "rowspan": int(c.get("rowspan") or 1)})
            if cells:
                rows.append(cells)
            if tr.getparent() is not None and tr.getparent().tag == "thead":
                header_rows += 1
    return {"kind": "table", "level": 1, "id": "", "label": "", "html": "",
            "header_rows": header_rows, "rows": rows, "foot_html": ""}


def _esc_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def upgrade_tables(project):
    """Convert any old-style table block (a JATS string in "html") to the
    row-and-cell shape the editor edits. Returns True if anything changed."""
    changed = False
    for b in project.get("blocks", []):
        if b.get("kind") != "table" or "rows" in b:
            continue
        new = table_block_from_jats(b.get("html", ""))
        new["id"] = b.get("id") or ""
        new["label"] = b.get("label", "")
        new["html"] = b.get("caption", "")
        b.clear()
        b.update(new)
        changed = True
    return changed


_TAB_ROW = re.compile(r"\S\t+\S")


def _tab_cells(html):
    """The cells of one tab-separated line, or None if it has no inner tab.
    A single leading tab is a paragraph indent, not a column."""
    text = re.sub(r"<[^>]+>", "", html or "").lstrip("\t ")
    return text.split("\t") if _TAB_ROW.search(text) else None


def find_tabbed_runs(blocks, min_rows=2):
    """(first, last) block indexes of runs of paragraphs laid out with tabs
    -- a table typed as text rather than set as an InDesign table."""
    runs, start = [], None
    for i, b in enumerate(blocks + [{"kind": "end"}]):
        cells = _tab_cells(b.get("html")) if b.get("kind") == "p" else None
        if cells is not None and start is None:
            start = i
        elif cells is None and start is not None:
            if i - start >= min_rows:
                runs.append((start, i - 1))
            start = None
    return runs


def _join_paras(inline_list):
    return "".join(f"<p>{jats_inline_to_editor(x)}</p>" for x in inline_list)


def piece_to_project(piece, issue_meta, seq, source_filename=""):
    """A parsed Piece -> the editable project JSON.

    The Piece already speaks the tool's inline micro-format, so this is mostly
    a rename. The two places it is not: block kinds that carry an extra field
    (a heading's level, a figure's file, a table's markup) arrive as longer
    tuples, and references arrive as display text rather than Word paragraphs
    -- which they always were conceptually, and now are literally."""
    blocks = []
    for item in piece.body_blocks:
        kind, content = item[0], item[1]
        extra = item[2] if len(item) > 2 else None
        h = jats_inline_to_editor(content)
        if kind == "subhed":
            blocks.append({"kind": "heading", "level": int(extra or 1), "html": h})
        elif kind == "figure":
            # InDesign links its graphics, so unlike Word the original filename
            # survives. It is the production filename, not the one that will be
            # attached in OJS, so the renderer still warns until it is checked.
            blocks.append({"kind": "figure", "level": 1, "html": h,
                           "file": extra or "", "label": "", "alt": "",
                           "position": "float"})
        elif kind == "table":
            n = sum(1 for b in blocks if b["kind"] == "table") + 1
            blocks.append(table_block(extra) if isinstance(extra, dict)
                          else table_block_from_jats(content))
            blocks[-1]["id"] = f"tbl-{n}"
        elif kind in ("p", "blockquote", "verse", "verse-break", "epigraph",
                      "epigraph-source", "fig-caption", "divider"):
            blocks.append({"kind": kind, "level": 1, "html": h})
        else:
            blocks.append({"kind": "p", "level": 1, "html": h})

    warnings = list(piece.warnings)
    for first, last in find_tabbed_runs(blocks):
        warnings.append(
            f"Body paragraphs {first + 1}-{last + 1} are laid out with tabs and "
            "look like a table typed as text. Use \"Find tabbed tables\" in "
            "the Body tab to turn them into a real table.")

    notes = []
    for note_blocks in piece.notes:
        parts = []
        for j, (kind, xml_text) in enumerate(note_blocks):
            if j == 0:
                xml_text = re.sub(r"^\s*\d+\.\s*\t?\s*", "", xml_text)
            parts.append({"kind": "q" if kind == "q" else "p",
                          "html": jats_inline_to_editor(xml_text)})
        notes.append({"parts": parts})

    ref_groups = []
    counter = 0
    for g in piece.ref_groups:
        refs = []
        for entry in g.get("html", []):
            counter += 1
            refs.append({"id": f"cit{counter:03d}",
                         "html": jats_inline_to_editor(entry)})
        if refs:
            ref_groups.append({"title": " ".join(g["title"].split()) or "References",
                               "refs": refs})

    project = {
        "id": "p" + uuid.uuid4().hex[:10],
        "created": time.time(),
        "modified": time.time(),
        "source_filename": source_filename,
        "meta": {
            "title": " ".join(piece.title.split()),
            "subtitle": " ".join((piece.subtitle or "").split()),
            "authors": " ".join(piece.byline.split()),
            "section": piece.section or "",
            "doi": piece.doi or "",
            "fpage": str(piece.fpage or piece.toc_page or ""),
            "lpage": str(piece.lpage or ""),
            "short_title": " ".join((getattr(piece, "short_title", "") or "").split()),
            "orcids": "",
            "issue_number": issue_meta.get("issue_number", ""),
            "year": issue_meta.get("year", ""),
            "season": issue_meta.get("season", ""),
            "issue_editors": " and ".join(issue_meta.get("editors") or []),
            "epub_date": "",
            # Filled in by hand once the article is up on OJS: the PDF galley
            # and the article's landing page, which the HTML galley's PDF and
            # Share buttons point at.
            "pdf_url": "",
            "article_url": "",
            # "cc" or "copyright"; blank takes bcs_config.RIGHTS_DEFAULT
            "rights": "",
            "seq": seq,
            "reviewer_affiliation": piece.reviewer_affiliation or "",
            "keywords": list(piece.keywords),
            "abstract_html": _join_paras(piece.abstract),
            "book_info_html": _join_paras(piece.book_info),
            "ack_html": _join_paras(piece.acknowledgements),
            "funding_html": _join_paras(getattr(piece, "funding", [])),
            "ethics_html": _join_paras(getattr(piece, "ethics", [])),
            "bios_html": _join_paras(piece.bios),
        },
        "blocks": blocks,
        "notes": notes,
        "ref_groups": ref_groups,
        "bibliography": bool(piece.bibliography),
        "warnings": warnings,
    }
    # Bios matched from the Contributors page arrive knowing whose they are:
    # give the Metadata tab one named box per contributor rather than one
    # field to be sorted out by surname later.
    names = getattr(piece, "bio_names", [])
    if piece.bios and len(names) == len(piece.bios):
        project["meta"]["bios"] = [{"name": n, "html": _join_paras([h])}
                                   for n, h in zip(names, piece.bios)]
    return refresh_citations(project)


# =============================================================================
# 5. PROJECT STORE -- one JSON file per article in projects/
# =============================================================================

def _path(pid):
    if not re.match(r"^p[0-9a-f]{10}$", pid or ""):
        raise ValueError("bad project id")
    return PROJECTS_DIR / f"{pid}.json"


def save_project(project):
    PROJECTS_DIR.mkdir(exist_ok=True)
    project["modified"] = time.time()
    # Stamp the format version on every save. Without this, a future change to
    # the shape of this file breaks every existing draft with no way
    # to tell which format a given file is inn
    from bcs_profiles import PROJECT_FORMAT_VERSION
    project.setdefault("format_version", PROJECT_FORMAT_VERSION)
    _path(project["id"]).write_text(
        json.dumps(project, ensure_ascii=False, indent=1), encoding="utf-8")
    return project


def load_project(pid):
    project = json.loads(_path(pid).read_text(encoding="utf-8"))
    # A Bibliography of British Columbia imported before the tool knew its
    # sections: sort its entries back under their heads (in memory; the
    # editor saves it the next time the draft is saved).
    if project.get("bibliography"):
        from bcs_bibliography import regroup_old_draft
        regroup_old_draft(project)
    return project


def media_dir(pid):
    """Where a draft's uploaded audio files live: projects/media/<pid>/. The
    blocks store only the filename, as they do for figures."""
    _path(pid)                      # same id check
    return PROJECTS_DIR / "media" / pid


def delete_project(pid):
    """Deletes the working draft only. The preservation copy in archive/ is
    left alone -- see ARCHIVE_DIR in app.py."""
    _path(pid).unlink(missing_ok=True)
    (PROJECTS_DIR / f"{pid}.xml").unlink(missing_ok=True)
    (PROJECTS_DIR / f"{pid}.archival.xml").unlink(missing_ok=True)
    shutil.rmtree(media_dir(pid), ignore_errors=True)


def list_projects():
    PROJECTS_DIR.mkdir(exist_ok=True)
    out = []
    for f in PROJECTS_DIR.glob("p*.json"):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
            out.append({
                "id": p["id"],
                "title": title_plain(p["meta"].get("title", "")),
                "title_html": title_html(p["meta"].get("title", "")),
                "authors": p["meta"].get("authors", ""),
                "section": p["meta"].get("section", ""),
                "issue": p["meta"].get("issue_number", ""),
                "modified": p.get("modified", 0),
                "has_xml": (PROJECTS_DIR / f"{p['id']}.xml").exists(),
            })
        except Exception:
            continue
    out.sort(key=lambda x: -x["modified"])
    return out
