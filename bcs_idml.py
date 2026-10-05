#!/usr/bin/env python3
"""
bcs_idml.py -- read an InDesign IDML package and split a BC Studies issue into
pieces in the same shape the rest of the tool already understands.
"""

import html
import re
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from bcs_config import SPECIAL_CHAR_FONTS
from bcs_styles import (
    BOUNDARY_STYLES, IGNORED_STYLES, SECTION_FOR_GROUP, decode_style_path,
    style_kind,
)

IDPKG = "{http://ns.adobe.com/AdobeInDesign/idml/1.0/packaging}"


# =============================================================================
# 1. THE PACKAGE
# =============================================================================

class IdmlPackage:
    """An IDML file, IDML is a zip of XML parts; it just puts the parts where the parser can reach them."""

    def __init__(self, source):
        self.zip = zipfile.ZipFile(source)
        self.designmap = self._xml("designmap.xml")
        self.styles = self._part("Resources/Styles.xml")
        self.stories = {}          # story id -> <Story> element
        self.spread_order = []     # spread ids, in page order
        self.frames = {}           # frame id -> {"story":.., "page":.., "spread":..}
        self.story_pages = {}      # story id -> [page label, ...] in frame order
        self.story_order = []      # story ids, in reading order
        self.images = {}           # spread id -> [image filename, ...]
        self.master_first_page = {}   # master spread id -> lowest page using it
        self.master_stories = set()   # stories that live on a master page
        self.hyperlinks = {}       # HyperlinkTextSource id -> URL
        self.page_spread = {}      # page label -> spread id
        self._char_styles = {}     # decoded name -> {"italic":bool,"bold":bool,"sup":bool}
        self._load_styles()
        self._load_hyperlinks()
        self._load_spreads()
        self._load_masters()
        self._load_stories()

    def page_is_blank(self, page, text_only=False):
        """No text frame on the page and no picture on its spread. Kept
        cautious: a spread with any image counts as not blank, because a
        frame's page is only a guess from its x position.

        text_only=True asks only "is there any text on this page?" -- right
        for the Bibliography, which has no figures, so a page with nothing
        but a picture on it is an advertisement (issue 230, page 144)."""
        name = str(page)
        if name not in self.page_spread:
            return False
        if any(f["page"] == name for f in self.frames.values()):
            return False
        return text_only or not self.images.get(self.page_spread[name])

    # -- zip helpers ---------------------------------------------------------

    def _xml(self, name):
        return ET.fromstring(self.zip.read(name))

    def _part(self, name):
        """A part referenced from designmap; IDML wraps each in an idPkg
        envelope whose single child is the thing you actually want."""
        try:
            root = self._xml(name)
        except KeyError:
            return None
        return root

    def _srcs(self, tag):
        return [e.get("src") for e in self.designmap.findall(f"{IDPKG}{tag}")]

    # -- character styles ----------------------------------------------------

    def _load_styles(self):
        """Resolve every character style to one of 3 things

        A style can inherit through BasedOn, so this walks the chain. Doing it
        by definition rather than by name means a house style called
        `citation book` or `Unnamed Style 7` is read correctly instead of
        guessed at."""
        if self.styles is None:
            return
        raw = {}
        for cs in self.styles.iter("CharacterStyle"):
            self_id = cs.get("Self", "")
            name = decode_style_path(self_id.split("/", 1)[-1])
            based = ""
            for p in cs.findall("./Properties/BasedOn"):
                based = decode_style_path((p.text or "").split("/", 1)[-1])
            raw[name] = {
                "font_style": cs.get("FontStyle", ""),
                "position": cs.get("Position", ""),
                "based_on": based,
            }

        def resolve(name, depth=0):
            if name in self._char_styles:
                return self._char_styles[name]
            info = raw.get(name)
            if info is None or depth > 8:
                out = {"italic": False, "bold": False, "sup": False}
            else:
                base = resolve(info["based_on"], depth + 1) if info["based_on"] and info["based_on"] != name \
                    else {"italic": False, "bold": False, "sup": False}
                fs = (info["font_style"] or "").lower()
                out = {
                    "italic": base["italic"] or "italic" in fs or "oblique" in fs,
                    "bold": base["bold"] or "bold" in fs or "black" in fs or "heavy" in fs,
                    "sup": base["sup"] or info["position"] == "Superscript",
                }
            self._char_styles[name] = out
            return out

        for name in list(raw):
            resolve(name)

    def char_style_effects(self, applied):
        name = decode_style_path((applied or "").split("/", 1)[-1])
        return self._char_styles.get(name, {"italic": False, "bold": False, "sup": False})

    # -- hyperlinks ----------------------------------------------------------

    def _load_hyperlinks(self):
        """Map each in-story hyperlink anchor to its URL. The anchor lives in
        the story; the URL is in designmap"""
        dests = {}
        for d in self.designmap.iter("HyperlinkURLDestination"):
            dests[d.get("Self")] = d.get("DestinationURL", "")
        for h in self.designmap.iter("Hyperlink"):
            src = h.get("Source")
            dest = ""
            for p in h.findall("./Properties/Destination"):
                dest = (p.text or "").strip()
            url = dests.get(dest, "")
            if src and url:
                self.hyperlinks[src] = url

    # -- spreads, pages, frames ---------------------------------------------

    def _load_spreads(self):
        for src in self._srcs("Spread"):
            root = self._part(src)
            if root is None:
                continue
            spread = root.find("Spread")
            if spread is None:
                continue
            sid = spread.get("Self")
            self.spread_order.append(sid)
            pages = [p.get("Name", "") for p in spread.findall("Page")]
            for name in pages:
                self.page_spread[name] = sid
            for pg in spread.findall("Page"):
                master = pg.get("AppliedMaster") or ""
                name = pg.get("Name", "")
                if master and name.isdigit():
                    prev = self.master_first_page.get(master)
                    if prev is None or int(name) < prev:
                        self.master_first_page[master] = int(name)
            imgs = []
            for link in spread.iter("Link"):
                uri = link.get("LinkResourceURI", "")
                if uri:
                    imgs.append(_basename_from_uri(uri))
            if imgs:
                self.images[sid] = imgs
            # Frames in document order. A frame's page is the nearest page by
            # index; a two-page spread has two, and InDesign does not record
            # which one a frame sits on, so left/right is decided by the x of
            # the frame's transform. Good enough for a first page number.
            for tf in spread.iter("TextFrame"):
                fid = tf.get("Self")
                story = tf.get("ParentStory")
                page = _page_for_frame(tf, pages)
                self.frames[fid] = {"story": story, "page": page, "spread": sid}
                if story:
                    self.story_pages.setdefault(story, []).append(page)
                    if story not in self.story_order:
                        self.story_order.append(story)

    def _load_masters(self):
        """Section openers -- "BOOK REVIEWS", "BIBLIOGRAPHY OF BRITISH
        COLUMBIA", "Contributors" -- are typeset on master pages, so their
        stories are attached to no document page at all and would sort to the
        end of the issue. Give each one the first page its master is applied
        to, which is where a reader meets it."""
        for src in self._srcs("MasterSpread"):
            root = self._part(src)
            if root is None:
                continue
            ms = root.find("MasterSpread")
            if ms is None:
                continue
            page = self.master_first_page.get(ms.get("Self"))
            if page is None:
                continue
            for tf in ms.iter("TextFrame"):
                story = tf.get("ParentStory")
                if not story:
                    continue
                self.frames.setdefault(tf.get("Self"),
                                       {"story": story, "page": str(page),
                                        "spread": ms.get("Self")})
                self.story_pages.setdefault(story, []).append(str(page))
                self.master_stories.add(story)
                if story not in self.story_order:
                    self.story_order.append(story)

    def _load_stories(self):
        for src in self._srcs("Story"):
            root = self._part(src)
            if root is None:
                continue
            for st in root.findall("Story"):
                self.stories[st.get("Self")] = st
        # Any story never placed on a spread still needs a slot at the end.
        for sid in self.stories:
            if sid not in self.story_order:
                self.story_order.append(sid)
        self._sort_story_order()

    def _sort_story_order(self):
        """Reading order is page order.

        Frames within a spread are stored in stacking order not reading
        order so walking spreads alone puts a sidebar before the article it
        sits beside and, in issue 229, put the whole Bibliography of British
        Columbia inside the last book review. Sorting by the lowest page a
        story appears on fixes that; ties keep their original order."""
        first = {}
        for sid, pages in self.story_pages.items():
            nums = [int(x) for x in pages if str(x).isdigit()]
            if nums:
                first[sid] = min(nums)
        order = list(self.story_order)
        # On a tie, a master-page story comes first: it is the section opener
        # standing at the head of the pages its master is applied to.
        self.story_order = sorted(
            order,
            key=lambda sid: (first.get(sid, 10 ** 6),
                             0 if sid in self.master_stories else 1,
                             order.index(sid)))

    # -- issue metadata ------------------------------------------------------

    def issue_meta(self):
        """The masthead knows the issue number; nothing else in the file does
        reliably. 'bc studies no. 229, Spring 2026' is the running head, and
        the .indd filename is the fallback."""
        number = year = season = ""
        for st in self.stories.values():
            text = " ".join(_story_plain(st).split())
            if len(text) > 300:
                continue
            m = re.search(r"bc\s*studies\s*,?\s*no\.?\s*(\d{2,4})\s*,?\s*"
                          r"(Spring|Summer|Autumn|Fall|Winter)?\s*(\d{4})?",
                          text, re.I)
            if not m:
                m = re.search(r"\bNumber\s+(\d{2,4})\s+"
                              r"(Spring|Summer|Autumn|Fall|Winter)?\s*(\d{4})?",
                              text, re.I)
            if m:
                number = number or m.group(1)
                season = season or (m.group(2) or "")
                year = year or (m.group(3) or "")
            if number and year:
                break
        name = self.designmap.get("Name", "")
        if not number:
            m = re.search(r"(\d{3})", name)
            number = m.group(1) if m else ""
        return {"issue_number": number, "year": year, "season": season.title(),
                "editors": self._masthead_editors(), "indd_name": name}

    _EDITOR_ROLE_RE = re.compile(r"^Editors?\s*:\s*(.+)$", re.I)

    def _masthead_editors(self):
        """Issue editors from a masthead with 'Editor: Name' lines, if the
        file has one (the printed masthead usually is not in the InDesign
        file). Guest editors and special-issue titles are not collected."""
        editors = []

        def split_names(names):
            return [w.strip(" .") for w in re.split(r"\s*(?:,|\band\b|&)\s*", names)
                    if w.strip(" .")]

        for st in self.stories.values():
            lines = [" ".join(l.split()) for l in _story_lines(st)]
            lines = [l for l in lines if l]
            if sum(len(l) for l in lines) > 3000:
                continue
            for line in lines:
                m = self._EDITOR_ROLE_RE.match(line)
                if m:
                    for who in split_names(m.group(1)):
                        if who not in editors:
                            editors.append(who)
        return editors


def _basename_from_uri(uri):
    from urllib.parse import unquote
    return unquote(uri.rsplit("/", 1)[-1])


def _page_for_frame(tf, pages):
    """Which page of the spread a frame sits on. IDML gives frames a transform
    relative to the spread origin; on a two-page spread the left page is the
    negative half With one page there is nothing to decide"""
    if not pages:
        return ""
    if len(pages) == 1:
        return pages[0]
    tm = (tf.get("ItemTransform") or "").split()
    x = float(tm[4]) if len(tm) >= 6 else 0.0
    return pages[0] if x < 0 else pages[-1]


def _story_plain(story):
    return "".join(c.text or "" for c in story.iter("Content"))


def _story_lines(story):
    """The story's text one paragraph per item -- <Br/> ends a paragraph."""
    lines, cur = [], []
    for el in story.iter():
        if el.tag == "Content":
            cur.append(el.text or "")
        elif el.tag == "Br":
            lines.append("".join(cur))
            cur = []
    lines.append("".join(cur))
    return lines


# =============================================================================
# 2. INLINE CONTENT
#
#    One CharacterStyleRange at a time turned into JATS inline markup. The
#    weird cases are all structural rather than typographic: a <Footnote>
#    is a whole note sitting inside the sentence it belongs to, a <Change>
#    element is an un-accepted edit, and <Br/> ends a paragraph rather than
#    breaking a line
# =============================================================================

_ACE_RE = re.compile(r"<\?ACE \d+\?>")
# A private marker standing in for an InDesign auto-number glyph while a
# paragraph is being built. It never reaches the output.
_MARK = "\uE000"


def _esc(text):
    return html.escape(text or "", quote=False)


_SPECIAL_OPEN = '<styled-content style-type="special-characters">'
# characters that belong to the same word as a special-character glyph: no
# whitespace, no tag brackets, no entity ampersands, no sentence punctuation
# (the right single quote stays in: it is a letter in Nisg̱a’a and Kwakwa̱ka̱ʼwakw)
_WORD_CHARS = r'[^\s<>&.,;:!?()\[\]"\u201c\u201d\u2018/\u2014\u2013]'


def font_is_special(font, text=""):
    """True when a run's font override marks it as special characters.

    BC Studies sets Indigenous-language words glyph by glyph: the body font
    (Adobe Caslon Pro) for the Latin letters and First Nations Unicode,
    Aboriginal Serif, Junicode or BabelStone Roman for the ones it lacks --
    and sometimes Cambria or Times New Roman for a single combining mark or
    IPA letter. The named fonts are always special; any other override is
    special only when it covers a glyph or two of non-ASCII text, which is
    the patch-one-character pattern and never body copy."""
    f = (font or "").strip()
    if not f:
        return False
    low = f.lower()
    if any(k.lower() in low for k in SPECIAL_CHAR_FONTS):
        return True
    t = (text or "").strip()
    return bool(t) and len(t) <= 3 and all(ord(c) > 127 for c in t)


def merge_special_runs(xml):
    """Grow each special-characters run to the whole word it sits in and merge
    neighbours, so 'l<sc>ə</sc>k<sc>ʷ</sc>...' becomes one run around ləkʷəŋən
    rather than confetti around every glyph. Tags inside the word (an
    <italic> that starts mid-word) stop the growth, which is safe: the run
    just stays smaller."""
    if _SPECIAL_OPEN not in xml:
        return xml
    close = "</styled-content>"
    prev = None
    while prev != xml:
        prev = xml
        # grow left and right over word characters
        xml = re.sub(r"(" + _WORD_CHARS + r"+)" + re.escape(_SPECIAL_OPEN),
                     lambda m: _SPECIAL_OPEN + m.group(1), xml)
        xml = re.sub(re.escape(close) + r"(" + _WORD_CHARS + r"+)",
                     lambda m: m.group(1) + close, xml)
        # merge two runs with nothing but word characters between them
        xml = re.sub(re.escape(close) + r"(" + _WORD_CHARS + r"*)" + re.escape(_SPECIAL_OPEN),
                     lambda m: m.group(1), xml)
    # a run that is only whitespace or empty says nothing
    xml = re.sub(re.escape(_SPECIAL_OPEN) + r"(\s*)" + re.escape(close), r"\1", xml)
    return xml


_EXT_PAIR_RE = re.compile(
    r'(<ext-link ext-link-type="uri" xlink:href="([^"]*)">)((?:(?!</ext-link>).)*)'
    r'</ext-link>(\s*)<ext-link ext-link-type="uri" xlink:href="\2">', re.S)


def merge_ext_links(xml):
    """InDesign often makes one link out of several hyperlink sources -- the
    URL text plus the space before it, or a URL broken across two runs. Each
    source came out as its own <ext-link>, so the galley showed the same
    address as two links side by side. Join neighbours that point at the
    same address."""
    prev = None
    while prev != xml:
        prev = xml
        xml = _EXT_PAIR_RE.sub(lambda m: m.group(1) + m.group(3) + m.group(4), xml)
    return xml


class InlineBuilder:
    """Accumulates runs and emits JATS inline markup, merging adjacent runs
    that share formatting so the output isn't a confetti of one-character
    <italic> elements."""

    def __init__(self):
        self.out = []
        self._buf = []
        self._fmt = None

    def text(self, s, italic=False, bold=False, sup=False, smallcaps=False,
             special=False):
        if not s:
            return
        fmt = (italic, bold, sup, smallcaps, special)
        if fmt != self._fmt:
            self.flush()
            self._fmt = fmt
        self._buf.append(s)

    def flush(self):
        if not self._buf:
            return
        s = _esc("".join(self._buf))
        italic, bold, sup, smallcaps, special = self._fmt or (False,) * 5
        if smallcaps:
            s = f'<sc>{s}</sc>'
        if italic:
            s = f"<italic>{s}</italic>"
        if sup:
            s = f"<sup>{s}</sup>"
        if special:
            s = f'{_SPECIAL_OPEN}{s}</styled-content>'
        self.out.append(s)
        self._buf = []

    def raw(self, s):
        self.flush()
        self._fmt = None
        self.out.append(s)

    def value(self):
        self.flush()
        return "".join(self.out)

    def is_empty(self):
        return not self.out and not self._buf


def _split_page_number(raw):
    """A table-of-contents entry ends with the page it points at. InDesign
    writes that number after an auto-number glyph, or after a tab, and usually
    sets it in small caps. Any of the three is enough to tell the number from
    the title it follows -- which matters when the title itself ends in a year.
    """
    for sep in (_MARK, "\t"):
        if sep in raw:
            head, _, tail = raw.rpartition(sep)
            digits = _plain(tail)
            if digits.isdigit():
                return int(digits), head.replace(_MARK, "").strip()
    m = re.search(r"<sc>\s*(\d{1,4})\s*</sc>\s*$", raw)
    if m:
        return int(m.group(1)), raw[:m.start()].replace(_MARK, "").strip()
    return None, raw.replace(_MARK, "").strip()


@dataclass
class RawPara:
    """One paragraph as it came out of a story: its style, its inline markup,
    and anything that hung off it."""
    style: str = ""             # decoded paragraph style path
    html: str = ""              # JATS inline markup, markers removed
    footnotes: list = field(default_factory=list)   # [[(kind, inline_xml), ...], ...]
    table: dict = field(default_factory=dict)       # a JATS-ready table, if any
    page_hint: int = None       # page number printed after an auto-number glyph
    html_before_page: str = ""  # the paragraph without that trailing number


class StoryReader:
    """Walks one <Story> and yields RawParas.

    Two things about IDML make this less obvious than it sounds.

    First, paragraph boundaries are <Br/> characters, not the ranges. A single
    ParagraphStyleRange can hold several paragraphs, and a single paragraph can
    run across several ranges, so the reader carries an open paragraph across
    ranges and closes it on <Br/>.

    Second, the tree is not flat. A ParagraphStyleRange can sit *inside* a
    HyperlinkTextSource -- which is how InDesign builds a generated table of
    contents, where each entry is a link -- so the walk has to descend into
    containers rather than reading only the story's direct children. 
    """

    # Containers that hold content but say nothing about it.
    _TRANSPARENT = {"HyperlinkTextSource", "XMLElement", "Group",
                    "TextVariableInstance"}
    # Structural elements with no text in them.
    _SKIP = {"Properties", "TextWrapPreference", "InCopyExportOption",
             "StoryPreference", "ObjectStyleRange", "AnchoredObjectSetting"}

    def __init__(self, pkg, story, note_counter):
        self.pkg = pkg
        self.story = story
        self.note_counter = note_counter   # a one-item list, shared per piece
        self.paras = []
        self._cur = InlineBuilder()
        self._cur_style = ""
        self._cur_notes = []
        self._cur_table = {}

    def read(self):
        self._walk_container(self.story)
        self._close()
        return [p for p in self.paras if p.html.strip() or p.table or p.footnotes]

    # -- paragraph bookkeeping ----------------------------------------------

    def _close(self):
        raw = merge_ext_links(merge_special_runs(self._cur.value()))
        page, before = _split_page_number(raw)
        html_out = raw.replace(_MARK, "")
        if html_out.strip() or self._cur_table or self._cur_notes:
            self.paras.append(RawPara(style=self._cur_style, html=html_out,
                                      footnotes=self._cur_notes,
                                      table=self._cur_table,
                                      page_hint=page,
                                      html_before_page=before))
        self._cur = InlineBuilder()
        self._cur_notes = []
        self._cur_table = {}

    # -- the walk ------------------------------------------------------------

    def _walk_container(self, node):
        """Find ParagraphStyleRanges wherever they are, including nested inside
        hyperlink and XML-element wrappers."""
        for child in node:
            tag = child.tag
            if tag == "ParagraphStyleRange":
                self._enter_para_style(child)
                self._walk_children(child, False, False, False, False)
            elif tag in self._TRANSPARENT or tag == "Change":
                self._walk_container(child)
            elif tag in self._SKIP:
                continue

    def _enter_para_style(self, psr):
        style = decode_style_path(
            (psr.get("AppliedParagraphStyle") or "").split("/", 1)[-1])
        if style:
            self._cur_style = style

    def _walk_children(self, node, italic, bold, sup, smallcaps,
                       in_deleted=False, link=None, font=""):
        for child in node:
            tag = child.tag

            if tag == "Content":
                if in_deleted:
                    continue
                # <?ACE n?> are InDesign's auto-number and marker glyphs; the
                # numbers they stand for are generated at layout time and mean
                # nothing outside the page.
                text = _ACE_RE.sub(_MARK, child.text or "")
                text = text.replace("\u2028", " ")
                if link and text.strip():
                    self._cur.raw(
                        f'<ext-link ext-link-type="uri" xlink:href="{_esc(link)}">'
                        f"{_esc(text)}</ext-link>")
                else:
                    self._cur.text(text, italic, bold, sup, smallcaps,
                                   font_is_special(font, text))

            elif tag == "Br":
                self._close()

            elif tag == "Footnote":
                if in_deleted:
                    continue
                self.note_counter[0] += 1
                n = self.note_counter[0]
                self._cur.raw(f'<xref ref-type="fn" rid="fn{n}">{n}</xref>')
                self._cur_notes.append(self._read_footnote(child))

            elif tag == "Table":
                if in_deleted:
                    continue
                self._cur_table = self._read_table(child)

            elif tag == "HyperlinkTextSource":
                # A hyperlink whose text is whole paragraphs is a container;
                # one whose text is a phrase is a link. Tell them apart by
                # whether it holds paragraphs.
                if child.find("ParagraphStyleRange") is not None:
                    self._walk_container(child)
                else:
                    url = self.pkg.hyperlinks.get(child.get("Self"), "")
                    self._walk_children(child, italic, bold, sup, smallcaps,
                                        in_deleted, url or link, font)

            elif tag == "Change":
                # An IDML file straight out of production can still carry
                # tracked changes. Accept them: keep insertions, drop
                # deletions. Anything else would re-open an edit the editors
                # already decided.
                deleted = child.get("ChangeType") == "DeletedText"
                self._walk_children(child, italic, bold, sup, smallcaps,
                                    in_deleted or deleted, link, font)

            elif tag == "ParagraphStyleRange":
                self._enter_para_style(child)
                self._walk_children(child, False, False, False, False,
                                    in_deleted, link)

            elif tag == "CharacterStyleRange":
                eff = self.pkg.char_style_effects(child.get("AppliedCharacterStyle"))
                fs = (child.get("FontStyle") or "").lower()
                # a font override lives in Properties/AppliedFont
                af = child.find("./Properties/AppliedFont")
                run_font = (af.text or "").strip() if af is not None else ""
                self._walk_children(
                    child,
                    eff["italic"] or "italic" in fs or "oblique" in fs,
                    eff["bold"] or "bold" in fs or "black" in fs or "heavy" in fs,
                    eff["sup"] or child.get("Position") == "Superscript",
                    child.get("Capitalization") == "SmallCaps",
                    in_deleted, link, run_font)

            elif tag in self._SKIP:
                continue

            else:
                # Rectangle, anchored objects, XML elements: descend in case
                # they hold text.
                self._walk_children(child, italic, bold, sup, smallcaps,
                                    in_deleted, link, font)

    # -- footnotes -----------------------------------------------------------

    def _read_footnote(self, fn):
        """A footnote is a small story of its own: its own paragraphs, its own
        styles, sometimes a block quote. Returns [(kind, inline_xml), ...],
        which is the shape Piece.notes wants."""
        sub = StoryReader(self.pkg, fn, [0])
        sub.read()
        parts = []
        for p in sub.paras:
            if not p.html.strip():
                continue
            kind = "q" if style_kind(p.style) == "blockquote" else "p"
            text = p.html
            if not parts:
                # The visible note number is generated by InDesign, so it is
                # not in the file; any leading digits are a hand-typed number
                # and would double up against the one we generate.
                text = re.sub(r"^\s*\d{0,3}[.)]?\s*", "", text, count=1)
            parts.append((kind, text.strip()))
        return parts or [("p", "")]

    # -- tables --------------------------------------------------------------

    def _read_table(self, tbl):
        """IDML tables are cell-addressed rather than row-nested: every Cell
        carries a 'column:row' name, and a merged cell carries RowSpan and
        ColumnSpan and simply leaves out the cells it covers. Rebuild rows of
        real cells from that in reading order.

        Footnotes anchored inside a cell are numbered in the same sequence as
        the running text so they are handed back to the paragraph holding
        the table rather than dropped with the cell's own reader."""
        header_rows = int(tbl.get("HeaderRowCount") or 0)
        rows = (header_rows + int(tbl.get("BodyRowCount") or 0)
                + int(tbl.get("FooterRowCount") or 0))
        cols = int(tbl.get("ColumnCount") or 0)
        at = {}
        for cell in tbl.findall("Cell"):
            name = cell.get("Name", "")
            if ":" not in name:
                continue
            c, r = name.split(":", 1)
            c, r = _int(c), _int(r)
            if c is None or r is None or not (0 <= r < rows and 0 <= c < cols):
                continue
            sub = StoryReader(self.pkg, cell, self.note_counter)
            sub.read()
            for p in sub.paras:
                self._cur_notes.extend(p.footnotes)
            at[(r, c)] = {
                "html": " ".join(p.html.strip() for p in sub.paras
                                 if p.html.strip()).strip(),
                "rowspan": max(1, _int(cell.get("RowSpan")) or 1),
                "colspan": max(1, _int(cell.get("ColumnSpan")) or 1),
            }
        # Some InDesign versions also write out the cells a merge covers;
        # they must not come back as cells of their own.
        covered = set()
        for (r, c), cell in sorted(at.items()):
            if (r, c) in covered:
                continue
            for dr in range(cell["rowspan"]):
                for dc in range(cell["colspan"]):
                    if dr or dc:
                        covered.add((r + dr, c + dc))
        grid = []
        for r in range(rows):
            grid.append([dict(at[(r, c)], th=r < header_rows)
                         for c in range(cols)
                         if (r, c) in at and (r, c) not in covered])
        return {"rows": rows, "cols": cols, "header_rows": header_rows,
                "grid": grid}


# =============================================================================
# 3. PIECES
# =============================================================================

@dataclass
class Piece:
    """One article, review, or review essay. Field-for-field the same as the
    DOCX parser's Piece, so bcs_editor.piece_to_project needs no change."""
    section: str = ""
    byline: str = ""
    title: str = ""
    subtitle: str = ""
    reviewer_affiliation: str = ""
    book_info: list = field(default_factory=list)
    review_books: list = field(default_factory=list)
    abstract: list = field(default_factory=list)
    keywords: list = field(default_factory=list)
    body_blocks: list = field(default_factory=list)     # (kind, inline_xml)
    acknowledgements: list = field(default_factory=list)
    funding: list = field(default_factory=list)
    ethics: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    ref_groups: list = field(default_factory=list)      # {"title":.., "html":[..]}
    bibliography: bool = False
    bios: list = field(default_factory=list)
    bio_names: list = field(default_factory=list)       # the author each bio is for
    figures: list = field(default_factory=list)         # {"file":.., "caption":..}
    toc_page: int = None
    doi: str = ""
    fpage: str = ""
    lpage: str = ""
    warnings: list = field(default_factory=list)


def _plain(inline_xml):
    return " ".join(re.sub(r"<[^>]+>", "", inline_xml or "").split())


def _looks_shouted(text):
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.8

class IssueParser:
    """Turns a package into pieces.

    Two passes. The first reads the table of contents, because the TOC is the
    only place in the file where the issue names its own sections and states
    each piece's first page -- InDesign records which frames a story flows
    through but not where in the story each frame begins, so a threaded story
    holding five book reviews cannot be split by page from the layout alone.
    The second pass reads the content and uses what the TOC said

    Piece boundaries come from bcs_styles.BOUNDARY_STYLES: certain styles open
    a new piece, and everything after one belongs to it until the next...
    the same rule the DOCX parser used and it fails the same way, a mis-styled
    title merges two pieces, but BC S' InDesign styles are applied far
    more consistently than a contributor's Word styles so it fails less often
    """

    def __init__(self, pkg):
        self.pkg = pkg
        self.pieces = []
        self.cur = None
        self.section = ""
        self.note_counter = [0]
        self.warnings = []
        self.toc_entries = []      # {"category","title","author","page"}
        self._pending_title = ""   # a divider heading that may name the piece
        self._title_is_placeholder = False
        self.categories = set()    # normalised category names, for the rule below

    # -- piece lifecycle -----------------------------------------------------

    def _open(self, section=None):
        self.cur = Piece(section=section or self.section)
        self.note_counter = [0]
        self.pieces.append(self.cur)
        return self.cur

    def _need(self):
        if self.cur is None:
            piece = self._open()
            if self._pending_title:
                piece.title = self._pending_title
                piece._title_placeholder = True
                self._pending_title = ""
        return self.cur

    # -- driver --------------------------------------------------------------

    def parse(self):
        stories = []
        for sid in self.pkg.story_order:
            story = self.pkg.stories.get(sid)
            if story is None:
                continue
            paras = StoryReader(self.pkg, story, [0]).read()
            if not paras:
                continue
            stories.append((sid, paras))

        # Pass 1 -- the table of contents.
        content = []
        for sid, paras in stories:
            if any(style_kind(p.style) == "toc" for p in paras):
                self._read_toc(paras)
            else:
                content.append((sid, paras))

        # Pass 2 -- everything else.
        for sid, paras in content:
            if self._is_furniture(paras):
                continue
            if self._is_caption_story(paras):
                self._attach_caption(sid, paras)
                continue
            self._read_story(sid, paras)

        return self._finalize()

    # -- pass 1: the table of contents ---------------------------------------

    _PAGE_TAIL = re.compile(r"[\s ]*(\d{1,4})\s*$")

    def _read_toc(self, paras):
        """Read the TOC into entries.

        The TOC is typeset not structured. A page number arrives after an
        auto-number glyph, after a tab, or in small caps at the end of the
        line, and the reader has already worked out which -- see
        `_split_page_number`. What is left here is knowing which paragraph
        style means what, and that an entry ends when its page number does."""
        category = ""
        pending = {"title": [], "author": "", "reviewer": ""}

        def close(page):
            title = " ".join(" ".join(pending["title"]).split())
            if title or pending["author"] or page:
                self.toc_entries.append({
                    "category": category,
                    "title": title,
                    "author": pending["author"] or pending["reviewer"],
                    "page": page,
                })
            pending["title"] = []
            pending["author"] = ""
            pending["reviewer"] = ""

        for p in paras:
            leaf = p.style.rsplit(":", 1)[-1]
            page = p.page_hint
            text = _plain(p.html_before_page if page else p.html)
            if not text and page is None:
                continue

            if leaf in ("CatagoryHeading", "BCStudiesHeading"):
                close(None)
                if page is not None and text:
                    # A category that is also an entry: "BIBLIOGRAPHY OF BC 159"
                    name = _detitle(text)
                    self.toc_entries.append({"category": name, "title": name,
                                             "author": "", "page": page})
                    self.categories.add(_key(text))
                elif text:
                    category = _detitle(text)
                    self.categories.add(_key(text))
            elif leaf in ("ArticleAuthor", "BookAuthor"):
                if leaf == "BookAuthor" and pending["title"]:
                    continue    # a second book in the same review
                close(None)
                pending["author"] = text
            elif leaf in ("ArticleAuthor", "BookAuthor"):
                close(None)
                pending["author"] = text

            elif leaf in ("ArticleTitle", "BookTitle"):
                if text:
                    pending["title"].append(text)
                if page is not None:
                    close(page)

            elif leaf == "BookReviewer":
                pending["reviewer"] = re.sub(r"^\s*reviewed by\s+", "", text,
                                             flags=re.I).strip()
                close(page)

        close(None)

    # -- pass 2 --------------------------------------------------------------

    def _is_furniture(self, paras):
        """Running heads, folios, jump lines, ad copy: one or two short
        paragraphs carrying no BC Studies style."""
        if len(paras) > 2:
            return False
        for p in paras:
            if style_kind(p.style) is not None:
                return False
        return len(" ".join(_plain(p.html) for p in paras)) < 200

    def _is_caption_story(self, paras):
        return all(style_kind(p.style) == "fig-caption" for p in paras)

    def _attach_caption(self, sid, paras):
        """A caption is typeset in its own frame, so it arrives detached from
        the article. Give it to the piece being read, and pair it with a linked
        graphic on the same spread if there is one."""
        spread = next((info["spread"] for info in self.pkg.frames.values()
                       if info["story"] == sid), None)
        if self.cur is None:
            self.warnings.append("Figure caption found before any article: "
                                 + _plain(paras[0].html)[:60])
            return
        files = self.pkg.images.get(spread, [])
        for i, p in enumerate(paras):
            self.cur.figures.append({
                "file": files[i] if i < len(files) else "",
                "caption": p.html.strip(),
            })

    def _read_story(self, sid, paras):
        pages = self.pkg.story_pages.get(sid, [])
        for p in paras:
            self._read_para(p, pages)

    # -- one paragraph -------------------------------------------------------

    def _read_para(self, p, pages):
        kind = style_kind(p.style)
        text = p.html.strip()
        plain = _plain(text)

        if kind == "toc":
            return

        # --- tables -----------------------------------------------------------
        # A table's number, its name, the sub-heads set between its parts and
        # its source note are all separate paragraphs around the table
        # object. Gather them while they keep coming and write the table out
        # once something else turns up.
        cur = self.cur
        if cur is not None and getattr(cur, "_tbl", None) is not None:
            if self._table_takes(cur._tbl, kind, p, plain):
                self._table_add(cur, kind, p, text, plain, pages)
                return
            self._flush_table(cur)
        if kind == "table-title":
            piece = self._need()
            self._new_table(piece)
            self._table_add(piece, kind, p, text, plain, pages)
            return

        if kind is None:
            if plain:
                self.warnings.append(
                    f"Unmapped paragraph style {p.style!r}: {plain[:70]}")
                self._need().body_blocks.append(("p", text))
            return

        group = p.style.split(":", 1)[0] if ":" in p.style else ""
        section = SECTION_FOR_GROUP.get(group, "")

        # --- section headings ------------------------------------------------
        # BC Studies typesets a section divider ("ARTICLES", "BOOK REVIEWS",
        # "SOUNDWORKS", "THIS SPACE HERE") with the same TITLE style an article
        # uses. The TOC is what tells them apart: a title that is also a
        # category name is a divider, and sets the section for what follows
        # rather than opening a piece of its own.
        if kind in ("title", "subtitle") and _key(plain) in self.categories:
            name = _detitle(plain)
            self.section = name
            if self.cur is not None and not _piece_has_content(self.cur):
                self.pieces.remove(self.cur)
            self.cur = None
            self._pending_title = name
            self._title_is_placeholder = True
            return

        # --- boundaries -------------------------------------------------------
        if p.style in BOUNDARY_STYLES:
            cur = self.cur
            if kind == "book-title" and cur is not None \
                    and not _piece_has_content(cur) and cur.title:
                piece = cur          # a titled review essay just opened
            elif kind == "book-title" and cur is not None and cur.review_books \
                    and not cur.byline and not (cur.body_blocks or cur.notes
                                                or cur.ref_groups):
                piece = cur          # a second book in the same review
            else:
                piece = self._open(section or self.section)
            self._pending_title = ""
            if kind == "title":
                piece.title = _detitle(plain)
                if _looks_shouted(plain):
                    piece.warnings.append(
                        "Title was set in capitals in InDesign and has been "
                        "title-cased -- check capitalisation before publishing.")
            else:
                piece.review_books.append(plain)
                piece.book_info.append(f"<italic>{_esc(plain)}</italic>")
            self._note_pages(piece, pages)
            return

        piece = self._need()
        self._note_pages(piece, pages)

        # --- everything else --------------------------------------------------
        if kind == "subtitle":
            piece.subtitle = plain
            if getattr(piece, "_title_placeholder", False):
                piece.title = _detitle(plain)      # the divider only named the section
                piece._title_placeholder = False
            else:
                piece.title = _join_title(piece.title, _detitle(plain))

        elif kind == "byline":
            piece.byline = re.sub(r"[\*†‡]+\d*\s*$", "", plain).strip()


        elif kind in ("book-author", "book-info", "book-title-following"):
            if kind == "book-title-following":
                piece.review_books.append(plain)
                piece.book_info.append(f"<italic>{_esc(plain)}</italic>")
            else:
                piece.book_info.append(text)

        elif kind == "reviewer":
            piece.byline = re.sub(r"[\*†‡]+\d*\s*$", "", re.sub(
                r"^\s*reviewed by\s+", "", plain, flags=re.I)).strip()

        elif kind == "reviewer-affiliation":
            piece.reviewer_affiliation = plain

        elif kind in ("heading", "heading2", "heading3") \
                and _is_bib_piece(piece, p.style):
            # The Bibliography of British Columbia: every head ("Books and
            # Chapters in Books", "Journal Articles", ...) opens one list of
            # entries. It is not a section of running text. (Issue 230 sets
            # three of its five heads in the Article sub-head style, so the
            # style alone cannot be trusted to say this.)
            piece._bib_next_title = bib_heading_title(plain)

        elif kind in ("heading", "heading2", "heading3"):
            level = {"heading": 1, "heading2": 2, "heading3": 3}[kind]
            label = plain.strip(" :").lower()
            if label in _REF_HEADS:
                # the printed head over the reference list: it becomes the
                # list's title, not an empty section in the body
                piece._pending_ref_title = plain.strip(" :")
            elif label in _NOTE_HEADS:
                pass    # the tool generates the Notes head itself
            else:
                piece.body_blocks.append(("subhed", text, level))

        elif kind in ("reference", "works-cited", "bibliography"):
            title = {"reference": "References", "works-cited": "Works Cited",
                     "bibliography": "Bibliography"}[kind]
            if kind == "bibliography":
                piece.bibliography = True
            bib_title = getattr(piece, "_bib_next_title", "")
            if bib_title:
                piece.ref_groups.append({"title": bib_title, "html": []})
                piece._bib_next_title = ""
            elif not piece.ref_groups:
                pending = getattr(piece, "_pending_ref_title", "")
                piece.ref_groups.append({"title": pending or title, "html": []})
                piece._pending_ref_title = ""
            piece.ref_groups[-1]["html"].append(text)

        elif kind == "fig-caption":
            piece.figures.append({"file": "", "caption": text})

        elif kind == "divider":
            piece.body_blocks.append(("divider", text))

        elif kind == "blockquote":
            piece.body_blocks.append(("blockquote", text))

        elif kind == "abstract":
            piece.abstract.append(text)

        elif kind == "bio":
            piece.bios.append(text)

        elif kind == "note":
            # A footnote paragraph that reached the body means the note was cut
            # loose from its anchor somewhere. Keep the text say so 
            piece.notes.append([("p", text)])
            piece.warnings.append(
                "A footnote paragraph was found in the running text rather "
                "than anchored -- check note numbering.")

        else:
            piece.body_blocks.append(("p", text))

        for note in p.footnotes:
            piece.notes.append(note)

        if p.table:
            self._new_table(piece)["tables"].append(([], p.table))

    # -- tables --------------------------------------------------------------

    def _new_table(self, piece):
        if getattr(piece, "_tbl", None) is not None:
            self._flush_table(piece)
        piece._tbl = {"label": "", "caption": [], "tables": [], "held": [],
                      "foot": []}
        return piece._tbl

    def _table_takes(self, g, kind, p, plain):
        """Does this paragraph still belong to the table being gathered?"""
        if kind == "table-title":
            return True
        if p.table and not plain:
            return True        # the empty paragraph the table is anchored in
        if kind in ("heading", "heading2", "heading3"):
            # A sub-head may sit between two parts of one table ("White Rock
            # detachment", "Surrey detachment"). Hold it... it becomes a row if
            # another table follows and an ordinary heading if text does.
            return plain.strip(" :").lower() not in _REF_HEADS | _NOTE_HEADS
        if g["tables"] and not g["held"] and plain \
                and (kind == "note" or _TABLE_NOTE.match(plain)):
            return True        # "Source: ..." set under the table
        return False

    def _table_add(self, piece, kind, p, text, plain, pages):
        self._note_pages(piece, pages)
        g = piece._tbl
        if kind == "table-title":
            if g["tables"] or g["held"]:
                g = self._new_table(piece)    # the next table's title
            leaf = p.style.rsplit(":", 1)[-1]
            m = _TABLE_LABEL.match(plain)
            if leaf == "TableNumber" and not g["label"]:
                g["label"] = plain.strip()
            elif m and not g["label"] and "<" not in text:
                g["label"] = m.group(1)
                if m.group(2).strip():
                    g["caption"].append(_esc(m.group(2).strip()))
            elif text.strip():
                g["caption"].append(text.strip())
        elif p.table:
            g["tables"].append((g["held"], p.table))
            g["held"] = []
        elif kind in ("heading", "heading2", "heading3"):
            g["held"].append((kind, text))
        elif plain:
            g["foot"].append(text)
        piece.notes.extend(p.footnotes)

    def _flush_table(self, piece):
        g = piece._tbl
        piece._tbl = None
        heads = {"heading": 1, "heading2": 2, "heading3": 3}
        if not g["tables"]:
            # a title with no table under it (the table may be a picture):
            # keep the paragraphs as they were
            if g["label"]:
                piece.body_blocks.append(("p", _esc(g["label"])))
            for c in g["caption"]:
                piece.body_blocks.append(("p", c))
        else:
            merged = _merge_tables(g["tables"])
            piece.body_blocks.append(("table", "", {
                "label": g["label"],
                "caption": " ".join(g["caption"]),
                "header_rows": merged["header_rows"],
                "rows": merged["rows"],
                "foot": g["foot"],
            }))
            if len(g["tables"]) > 1:
                piece.warnings.append(
                    f"{g['label'] or 'A table'} was set in InDesign as "
                    f"{len(g['tables'])} separate tables with sub-heads between "
                    "them. They have been joined into one table, with each "
                    "sub-head as a full-width row -- check it in the Body tab.")
        for kind, text in g["held"]:
            piece.body_blocks.append(("subhed", text, heads[kind]))

    # -- pages ---------------------------------------------------------------

    def _note_pages(self, piece, pages):
        """The pages a piece's story flows through. Only ever a fallback: the
        TOC is more precise for anything sharing a story with its neighbours."""
        nums = [n for n in (_int(x) for x in pages) if n]
        if nums:
            piece._story_pages = sorted(set(nums + getattr(piece, "_story_pages", [])))

    # -- finish --------------------------------------------------------------

    def _finalize(self):
        for p in self.pieces:
            if getattr(p, "_tbl", None) is not None:
                self._flush_table(p)
            _take_back_statements(p)
        kept = []
        for p in self.pieces:
            if not _piece_has_content(p):
                continue
            if not p.title and not p.byline and len(p.body_blocks) < 3 \
                    and not p.ref_groups and not p.book_info:
                first = p.body_blocks[0][1] if p.body_blocks else ""
                self.warnings.append(
                    "Dropped a scrap of front matter with no title: "
                    + _plain(first)[:60])
                continue
            kept.append(p)

        for piece in kept:
            if not piece.title and piece.review_books:
                piece.title = "; ".join(piece.review_books)
                piece.warnings.append(
                    "Review title defaulted to the book(s) under review -- "
                    "edit before publishing.")

        self._match_toc(kept)

        for i, piece in enumerate(kept):
            story_pages = getattr(piece, "_story_pages", [])
            if piece.toc_page:
                piece.fpage = str(piece.toc_page)
            elif story_pages:
                piece.fpage = str(story_pages[0])
            nxt = next((q.toc_page for q in kept[i + 1:] if q.toc_page), None)
            if piece.toc_page and nxt and nxt > piece.toc_page:
                last = nxt - 1
                # a blank page before the next piece (issue 230 leaves 144
                # empty after the Bibliography) is not part of this one
                while last > piece.toc_page and self.pkg.page_is_blank(
                        last, text_only=piece.bibliography):
                    last -= 1
                piece.lpage = str(last)
            elif story_pages:
                piece.lpage = str(story_pages[-1])
            elif piece.fpage:
                piece.lpage = piece.fpage

            # InDesign anchors NADA: a figure lives in its own frame, and
            # the file records where it sits on the page, not where it sits in
            # the argument. So captions land at the end and are moved by hand.
            for fig in piece.figures:
                piece.body_blocks.append(("figure", fig["caption"], fig["file"]))
            if piece.figures:
                piece.warnings.append(
                    f"{len(piece.figures)} figure(s) added at the end of the "
                    "article -- InDesign frames have no anchor. In the Body "
                    "tab, \"Place at first mention\" moves each one after the "
                    "paragraph that first cites it; drag or \"Move to\" the rest.")

        for piece in kept:
            if piece.bibliography and piece.byline:
                # "prepared by David Gill, mlis" (small caps in print) ->
                # "Prepared by David Gill, MLIS"
                from bcs_names import byline_parts
                role, names, degrees = byline_parts(piece.byline)
                piece.byline = ((role + " " if role else "") + names
                                + "".join(", " + d for d in degrees))
            if piece.bibliography and _key(piece.title) == _key(
                    "Bibliography of British Columbia"):
                piece.warnings = [w for w in piece.warnings
                                  if not w.startswith("Title was set in capitals")]

        if kept:
            kept[0].warnings.extend(self.warnings)
        self.pieces = kept
        return kept

    def _match_toc(self, pieces):
        """Match TOC entries to pieces, and take the section and first page
        from the match. Titles in a TOC are routinely shortened, so a prefix
        match on either side counts, and a matching byline is enough on its
        own."""
        used = set()
        for piece in pieces:
            pk = _key(piece.title)
            bk = _key(piece.byline)
            best = None
            for j, e in enumerate(self.toc_entries):
                if j in used or not (e["title"] or e["author"]):
                    continue
                tk, ak = _key(e["title"]), _key(e["author"])
                hit = (tk and pk and (pk.startswith(tk) or tk.startswith(pk)
                                      or _close_enough(pk, tk))) \
                    or (ak and bk and (bk.startswith(ak) or ak.startswith(bk)))
                if hit:
                    best = j
                    break
            if best is None:
                continue
            used.add(best)
            e = self.toc_entries[best]
            if e["page"]:
                piece.toc_page = e["page"]
            if e["category"]:
                piece.section = e["category"]


# The sections an article may close with that are statements about the
# research rather than part of the argument. They are set with the ordinary
# sub-head style, so the head's wording is all that tells them apart.
_BACK_HEADS = {
    "acknowledgements": "acknowledgements", "acknowledgments": "acknowledgements",
    "acknowledgement": "acknowledgements", "acknowledgment": "acknowledgements",
    "funding": "funding", "funding statement": "funding",
    "funding information": "funding", "funding sources": "funding",
    "financial support": "funding", "research funding": "funding",
    "ethics": "ethics", "ethics statement": "ethics", "ethical statement": "ethics",
    "ethics approval": "ethics", "ethical approval": "ethics",
    "research ethics": "ethics", "statement of ethics": "ethics",
    "ethics declaration": "ethics", "ethics declarations": "ethics",
}
_BACK_LABELS = {"acknowledgements": "Acknowledgements", "funding": "Funding",
                "ethics": "Ethics Statement"}


def _back_head(block):
    if block[0] != "subhed":
        return None
    return _BACK_HEADS.get(_plain(block[1]).strip(" :.").lower())


def _take_back_statements(piece):
    """Move a closing Acknowledgements / Funding / Ethics Statement run out of
    the body and into the piece's own fields, so the JATS can say what each
    one is (<ack>, <funding-group>, an ethics note) instead of carrying them
    as three more body sections.

    Only a run that closes the article is taken: from its first head to the
    end there may be nothing but those heads and plain paragraphs. A section
    called "Funding" in the middle of an article about museum funding stays
    where it is."""
    blocks = piece.body_blocks
    start = next((i for i, b in enumerate(blocks) if _back_head(b)), None)
    while start is not None:
        rest = blocks[start:]
        if all(_back_head(b) or b[0] in ("p", "blockquote") for b in rest):
            break
        start = next((i for i in range(start + 1, len(blocks))
                      if _back_head(blocks[i])), None)
    if start is None:
        return
    moved, dest = [], None
    for b in blocks[start:]:
        kind = _back_head(b)
        if kind:
            dest = {"acknowledgements": piece.acknowledgements,
                    "funding": piece.funding, "ethics": piece.ethics}[kind]
            if _BACK_LABELS[kind] not in moved:
                moved.append(_BACK_LABELS[kind])
        elif _plain(b[1]):
            dest.append(b[1])
    del blocks[start:]
    piece.warnings.append(
        "Moved " + ", ".join(moved) + " out of the body and into the Metadata "
        "tab, where each goes into the XML as its own element -- check them there.")


def _close_enough(a, b):
    """A TOC title is set by hand and routinely abbreviates -- "Bibliography of
    BC" for "Bibliography of British Columbia". A prefix test misses those, so
    fall back to a similarity score, tight enough that two different articles
    in the same issue will not collide."""
    from difflib import SequenceMatcher
    if len(a) < 8 or len(b) < 8:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.66


def _is_bib_piece(piece, style=""):
    """Is this the Bibliography of British Columbia?"""
    return bool(piece.bibliography
                or (style or "").startswith("Bibliography:")
                or "bibliograph" in (piece.section or "").lower()
                or _key(piece.title).startswith("bibliographyof"))


_BIB_SMALL = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in",
              "nor", "of", "on", "or", "the", "to", "with"}


def bib_heading_title(text):
    """A Bibliography head as a list title. The heads print in capitals, and
    what is typed under them is inconsistent ("Audiovisual materials",
    "Grey Literature"), so give them all the same title case."""
    text = " ".join(_detitle(text).split()).strip(" :.")
    words = text.split()
    out = []
    for i, w in enumerate(words):
        if 0 < i and w.lower() in _BIB_SMALL:
            out.append(w.lower())
        elif w[:1].islower():
            out.append(w[:1].upper() + w[1:])
        else:
            out.append(w)
    return " ".join(out)


def _piece_has_content(piece):
    return bool(piece.body_blocks or piece.ref_groups or piece.book_info
                or piece.notes or piece.figures)


def _join_title(title, subtitle):
    if not title:
        return subtitle
    if title.rstrip().endswith((":", "?", "!", "—", "–")):
        return f"{title} {subtitle}"
    return f"{title}: {subtitle}"


def _int(x):
    try:
        return int(str(x).strip())
    except (TypeError, ValueError):
        return None

def _key(title):
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())[:48]


def _detitle(text):
    """InDesign sets titles in all caps via a style attribute, but sometimes
    the caps are typed into the file. Title-case those so the XML doesn't
    shout, and leave anything already mixed-case alone."""
    if not _looks_shouted(text):
        return text
    small = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in",
             "nor", "of", "on", "or", "the", "to", "with"}
    # Place and organisation names that are acronyms, not words.
    keep_upper = {"bc", "ubc", "sfu", "unbc", "cnr", "cpr", "rcmp", "hbc",
                  "us", "usa", "uk"}
    words = text.split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        core = lw.strip(".,;:()")
        if core in keep_upper:
            out.append(lw.replace(core, core.upper()))
        elif 0 < i < len(words) - 1 and lw in small:
            out.append(lw)
        else:
            out.append(lw.capitalize())
    return " ".join(out)


_REF_HEADS = {"references", "works cited", "bibliography", "sources",
              "sources cited", "select bibliography"}
_NOTE_HEADS = {"notes", "endnotes"}
_TABLE_NOTE = re.compile(r"\s*(sources?|notes?)\s*[:.]", re.I)
_TABLE_LABEL = re.compile(r"\s*(table\s+[0-9ivxlc]+[a-z]?)\s*[.:\u2014\u2013-]?\s*(.*)$",
                          re.I | re.S)


def _merge_tables(parts):
    """One table from the InDesign table(s) gathered under one title.

    parts is [(held_heads, table)]: each table with the sub-heads set just
    above it. A sub-head becomes a full-width header row. A narrower table
    is widened by stretching the last cell of each of its rows, so every row
    of the result spans the same columns."""
    cols = max(t["cols"] for _h, t in parts) or 1
    rows, header_rows = [], 0
    for i, (heads, t) in enumerate(parts):
        for _kind, text in heads:
            rows.append([{"html": text, "th": True, "colspan": cols,
                          "rowspan": 1}])
        if i == 0 and not heads:
            header_rows = t["header_rows"]
        for row in t["grid"]:
            row = [dict(c) for c in row]
            if row and t["cols"] < cols:
                row[-1]["colspan"] += cols - t["cols"]
            rows.append(row)
    return {"cols": cols, "header_rows": header_rows, "rows": rows}


# =============================================================================
# 4. ONE-CALL ENTRY POINT
# =============================================================================

def preflight(idml_source):
    """List every paragraph style the file uses, and say which ones this tool
    does not recognise. IDML makes it cheap to fix, the
    styles are declared in the package, so they can be checked before anything
    is imported, while the person who applied them is still holding the file.

    Returns {"known": [(style, count)], "unknown": [(style, count, sample)]}.
    """
    pkg = IdmlPackage(idml_source)
    counts, samples = {}, {}
    for sid in pkg.story_order:
        story = pkg.stories.get(sid)
        if story is None:
            continue
        for para in StoryReader(pkg, story, [0]).read():
            counts[para.style] = counts.get(para.style, 0) + 1
            if para.style not in samples:
                samples[para.style] = _plain(para.html)[:80]
    known, unknown = [], []
    for style, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if style in IGNORED_STYLES:
            continue
        if style_kind(style) is None:
            unknown.append((style, n, samples.get(style, "")))
        else:
            known.append((style, n))
    return {"known": known, "unknown": unknown}


def _people(byline):
    from bcs_names import split_byline
    try:
        return [(s, g) for s, g in split_byline(byline or "") if s]
    except Exception:
        return []


def _words(text):
    """A name or phrase reduced for matching: no accents, no punctuation, lower
    case. "ḥapinyuuk" and "hapinyuuk" are the same word here, and so are
    "Naowarat (Ann) Cheeptham" and "Naowarat Ann Cheeptham"."""
    from bcs_jats_render import _name_key
    return _name_key(text).split()


def _bio_lead(para):
    """The part of a Contributors paragraph that names its subject: the small
    caps it opens with, or, when it opens some other way ("My name is
    ḥapinyuuk. ..."), its first sentence."""
    m = re.match(r"\s*<sc>(.*?)</sc>", para)
    if m:
        return _words(_plain(m.group(1)))
    first = re.split(r"(?<=[.!?])\s", _plain(para), maxsplit=1)[0]
    return _words(first[:160])


def _has_run(words, run):
    n = len(run)
    return n > 0 and any(words[i:i + n] == run for i in range(len(words) - n + 1))


def _find_bio(surname, given, leads):
    """Indexes of the Contributors paragraphs about this author. Tried in
    order, stopping at the first test that finds anyone: the whole name, then
    the surname with the first given name somewhere in the lead, then the
    surname alone. Words are compared whole, so "Ho" is not found inside
    "Hannah", and a surname written two ways ("Happynook/ḥapinyuuk") is
    looked for under either."""
    surnames = [w for w in (_words(x) for x in surname.split("/")) if w]
    first = (_words(given) or [""])[0]
    tests = [
        lambda L: any(_has_run(L, _words(given) + sn) for sn in surnames),
        lambda L: first and first in L and any(_has_run(L, sn) for sn in surnames),
        lambda L: any(_has_run(L, sn) for sn in surnames),
    ]
    for test in tests:
        hits = [i for i, lead in enumerate(leads) if test(lead)]
        if hits:
            return hits
    return []


def attach_contributor_bios(pieces):
    """The Contributors section prints one paragraph per author, opening with
    the name in small caps. Hand each article the paragraphs that name its
    authors, so the bios travel with the article into OJS (as <bio> inside
    <contrib>) and the galley's Contributor Bios box. Each bio is stored with
    the name of the author it was matched to, which fills the name box above
    it in the Metadata tab. The Contributors piece itself is left intact."""
    contrib_pieces = [p for p in pieces
                      if (p.section or "").strip().lower() == "contributors"
                      or (p.title or "").strip().lower() == "contributors"]
    if not contrib_pieces:
        return
    paras = []
    for cp in contrib_pieces:
        for item in cp.body_blocks:
            kind, content = item[0], item[1]
            if kind in ("p", "blockquote") and _plain(content):
                paras.append(content)
    if not paras:
        return
    leads = [_bio_lead(p) for p in paras]
    for piece in pieces:
        if piece in contrib_pieces or piece.bios:
            continue
        missing = []
        for surname, given in _people(piece.byline):
            name = " ".join(x for x in (given, surname) if x)
            hits = _find_bio(surname, given, leads)
            if len(hits) == 1:
                if paras[hits[0]] not in piece.bios:
                    piece.bios.append(paras[hits[0]])
                    piece.bio_names.append(name)
            elif len(hits) > 1:
                piece.warnings.append(
                    f"Several Contributors entries could be {name}'s -- "
                    "paste the right bio into the Metadata tab by hand.")
            else:
                missing.append(name)
        # Reviews and short pieces often have no bios at all; a gap is only
        # worth saying when the page covers some of a piece's authors.
        if piece.bios and missing:
            piece.warnings.append(
                "No bio on the Contributors page for " + ", ".join(missing)
                + " -- add one in the Metadata tab if the journal has it.")


def parse_issue(idml_source):
    """Read an IDML file (path or file-like) -> (pieces, issue_meta)."""
    pkg = IdmlPackage(idml_source)
    meta = pkg.issue_meta()
    pieces = IssueParser(pkg).parse()
    for i, piece in enumerate(pieces):
        if not piece.lpage and piece.fpage:
            piece.lpage = piece.fpage
    attach_contributor_bios(pieces)
    return pieces, meta


if __name__ == "__main__":
    import sys
    pieces, meta = parse_issue(sys.argv[1])
    print(meta)
    for i, p in enumerate(pieces, 1):
        print(f"{i:3}. [{p.section or '?':22}] {p.title[:58]:58} "
              f"{p.byline[:28]:28} pp.{p.fpage}-{p.lpage} "
              f"blocks={len(p.body_blocks)} notes={len(p.notes)} "
              f"refs={sum(len(g['html']) for g in p.ref_groups)} "
              f"figs={len(p.figures)}")
