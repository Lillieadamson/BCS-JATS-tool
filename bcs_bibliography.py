#!/usr/bin/env python3
"""
bcs_bibliography.py -- the Bibliography of British Columbia.

Every issue of BC Studies closes with Bibliography of British
Columbia: a list of new books, chapters, articles and theses, sorted into
sections under a head ("Books and Chapters in Books", "Journal Articles",
"Theses, Dissertations, and Graduate Projects", "Audiovisual Materials",
"Grey Literature", ...). The entries are Chicago bibliography style, with
the authors set in small caps and, for books, the page count and ISBN:

    APPEL, SERAFINA. "Commemoration and (Re)Conciliation." In Toppling
        Things, edited by Tomas Macsotay and Nausikaä El-Mecky. Series 35.
        Brill, 2025. 380 pp. 9789004712638 (hc).
    BAIRD, IAN G. "Letters from Mio." Asian Ethnicity 26, no. 2 (2025):
        213-49. https://doi.org/10.1080/14631369.2024.2446367.
    BRAUN, JOY ANNE. "Protecting Vulnerable Persons." PhD, University of
        British Columbia, 2025. https://doi.org/10.14288/1.0448058.

That is regular enough to read field by field, and different enough from an
article's Works Cited (author-date) that the general reader in bcs_editor
gets it wrong: it typed chapters as journal articles, read "Danya A. Fox"
as a person called "A", and took "host" for a name. This module reads it
properly.

HOW AN ENTRY IS READ
--------------------
1. The authors run from the start of the entry to the first full stop that
   is followed by a title -- an opening quotation mark or italics. Initials
   ("Andrea J.", "Quentin C.B. Cronk") never are, so they are not mistaken
   for the end. If that fails, the end of the small caps is used.
2. The section head says what kind of work it is; the entry itself can
   overrule it (a quoted title followed by "In" and an italic title is a
   chapter wherever it is filed).
3. The rest is read by pattern: "edited by ...", "Publisher, 2025.",
   "380 pp.", an ISBN with its binding, "17, no. 4 (2025): 213-49.", a
   degree and institution, a DOI or URL.

Whatever is read is tagged inside the printed text (<mixed-citation>, which
the galley shows) and written out again as structured fields
(<element-citation>, for indexes and the archive). Nothing printed is ever
dropped: anything not recognised stays in the text untagged.

IF THE BIBLIOGRAPHY CHANGES SHAPE
---------------------------------
New section heads: add a line to SECTION_KINDS. A new kind of entry: add its
pattern to analyze_bib_entry() and its fields to build_bib_element_citation().
"""

import html
import re

esc = lambda t: html.escape(t, quote=False)
esc_attr = lambda t: html.escape(t, quote=True)

# =============================================================================
# 1. SECTIONS
# =============================================================================

# A word in the section head -> what the entries under it are. Checked in
# order; the first that appears in the head wins.
SECTION_KINDS = [
    ("thes", "thesis"),            # Theses, Dissertations, and Graduate Projects
    ("dissertation", "thesis"),
    ("journal", "journal"),        # Journal Articles
    ("article", "journal"),
    ("audio", "audiovisual"),      # Audiovisual Materials
    ("film", "audiovisual"),
    ("podcast", "audiovisual"),
    ("grey", "report"),            # Grey Literature
    ("gray", "report"),
    ("report", "report"),
    ("book", "book"),              # Books and Chapters in Books
    ("chapter", "book"),
]

# The standard heads, offered in the editor's References tab when a list is
# added to the Bibliography.
STANDARD_HEADS = [
    "Books and Chapters in Books",
    "Journal Articles",
    "Theses, Dissertations, and Graduate Projects",
    "Audiovisual Materials",
    "Grey Literature",
]


def section_kind(head):
    h = (head or "").lower()
    for word, kind in SECTION_KINDS:
        if word in h:
            return kind
    return ""


# =============================================================================
# 2. NAMES
# =============================================================================

# Lower-case words that belong to the surname that follows them.
_PARTICLES = {"de", "da", "das", "do", "dos", "des", "di", "del", "della", "du", "la",
              "le", "van", "von", "der", "den", "ter", "ten", "al", "el", "bin",
              "ibn", "st.", "mac"}
_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}

# A role printed after the names: "..., eds." / "..., host".
_ROLE_TAIL = re.compile(
    r",?\s*\b(eds?|editors?|hosts?|comps?|compilers?|dirs?|directors?|"
    r"trans|translators?)\.?\s*$", re.I)
_ETAL = re.compile(r",?\s*\bet\s+al\.?\s*$", re.I)

_ROLE_GROUP = {"ed": "editor", "eds": "editor", "editor": "editor",
               "editors": "editor", "comp": "compiler", "comps": "compiler",
               "compiler": "compiler", "compilers": "compiler",
               "dir": "director", "dirs": "director", "director": "director",
               "directors": "director", "trans": "translator",
               "translator": "translator", "translators": "translator",
               "host": "host", "hosts": "host"}


def _chunks(text, lo):
    """Split a run of names at commas and "and", keeping where each chunk
    sits: [(chunk, start, end), ...] with start/end offsets into the entry."""
    out = []
    for m in re.finditer(r"[^,]+", text):
        part = m.group(0)
        start = lo + m.start()
        lead = re.match(r"\s*(?:and\s+|&\s*)?", part).end()
        core = part[lead:].rstrip()
        if core:
            out.append((core, start + lead, start + lead + len(core)))
    # "Reid and Natalie Ban" with no comma: split on " and " too
    final = []
    for core, s, e in out:
        pos = 0
        for m in re.finditer(r"\s+(?:and|&)\s+", core):
            final.append((core[pos:m.start()], s + pos, s + m.start()))
            pos = m.end()
        final.append((core[pos:], s + pos, e))
    return [(c, s, e) for c, s, e in final if c.strip()]


def _given_first(chunk, s):
    """ "Natalie C. Ban" -> (surname, given, surname span, given span)."""
    words = list(re.finditer(r"\S+", chunk))
    if len(words) == 1:
        w = words[0]
        return w.group(0), "", (s + w.start(), s + w.end()), None
    i = len(words) - 1
    while i > 1 and words[i - 1].group(0).lower() in _PARTICLES:
        i -= 1
    sur_lo = words[i].start()
    given_hi = words[i - 1].end()
    return (chunk[sur_lo:], chunk[:given_hi],
            (s + sur_lo, s + len(chunk)), (s, s + given_hi))


def read_names(text, lo=0, inverted_first=True):
    """A run of printed names -> list of people.

    Each person is a dict: surname, given (as printed), and the character
    spans of the whole name, the surname and the given names (offsets into
    the entry, given the run starts at lo), so the mixed-citation can tag
    them where they stand. The first name of an author list is printed
    surname-first; every other name, and every editor, given-name-first."""
    people = []
    chunks = _chunks(text, lo)
    i = 0
    while i < len(chunks):
        core, s, e = chunks[i]
        if core.lower().rstrip(".") in {x.rstrip(".") for x in _SUFFIXES} and people:
            people[-1]["given"] += ", " + core
            people[-1]["span"] = (people[-1]["span"][0], e)
            i += 1
            continue
        if i == 0 and inverted_first and len(chunks) > 1:
            g_core, g_s, g_e = chunks[1]
            people.append({"surname": core, "given": g_core,
                           "span": (s, g_e), "sur_span": (s, e),
                           "given_span": (g_s, g_e), "inverted": True})
            i += 2
            continue
        sur, giv, sur_span, giv_span = _given_first(core, s)
        people.append({"surname": sur, "given": giv, "span": (s, e),
                       "sur_span": sur_span, "given_span": giv_span,
                       "inverted": False})
        i += 1
    return people


def canonical_name(person):
    """Surname and given names for the structured citation. "Haegen, Thilo
    van der" is printed with the particle after the given name; in the
    structured form it goes back on the surname."""
    sur, giv = person["surname"].strip(), person["given"].strip()
    if re.search(r"(?:^|\s)[A-Z]$", giv):
        giv += "."          # "Ian G" -- the full stop closed the names
    if person.get("inverted"):
        words = giv.split()
        k = len(words)
        while k > 1 and words[k - 1].lower() in _PARTICLES:
            k -= 1
        if k < len(words):
            sur = " ".join(words[k:] + [sur])
            giv = " ".join(words[:k])
    return sur, giv


# =============================================================================
# 3. READING AN ENTRY
# =============================================================================

_MONTHS = ("January|February|March|April|May|June|July|August|September|"
           "October|November|December|Spring|Summer|Fall|Autumn|Winter")
# "https://doi.org/10.x/y" and, in older issues, "doi:10.x/y"
_DOI = re.compile(r"(?:https?://(?:dx\.)?doi\.org/|\bdoi:\s*)(10\.\S+?)(?=[.,;]?(?:\s|$))", re.I)
_URL = re.compile(r"https?://\S+?(?=[.,;]?(?:\s|$))")
_ISBN = re.compile(r"\b(97[89]\d{10}|\d{9}[\dX])\b(?:\s*\(([a-z. ]{1,12})\))?")
_SIZE = re.compile(r"\b(\d{1,5})\s+pp\.")
# the names end at the first full stop that does not close an initial
# ("edited by Larry B. Crowder. Open Book Publishers")
_EDITED = re.compile(
    r",?\s*(edited|translated|compiled)\s+by\s+(.+?)(?<!\b[A-Z])(?=\.\s|\.$)")
# "17, no. 4 (2025): 102276."  "136 (February 2025): 104679."  "13 (2025)."
_JOURNAL = re.compile(
    r"\s*(?P<vol>[A-Z]?\d[\w]*)?"
    r"(?:,\s*no\.\s*(?P<iss>[\w-]+))?"
    r"\s*\((?:(?P<month>(?:" + _MONTHS + r")(?:/(?:" + _MONTHS + r"))?)\.?\s+)?(?P<year>\d{4})\)"
    r"(?::\s*(?P<pages>[A-Za-z0-9.]+?(?:[–-]\w+)?))?(?=\.(?:\s|$)|$)")
# "PhD, University of British Columbia, 2025."
_THESIS = re.compile(
    r"\s*(?P<deg>[A-Z][A-Za-z.]{1,7}),\s+(?P<inst>[^,]+(?:,[^,0-9]+)*?),\s+"
    r"(?P<year>\d{4})\.")
# "Brill, 2025."  "Province of British Columbia, 2025."  "15 February 2025."
_PUB_YEAR = re.compile(
    r"(?:^|(?<=\.\s)|(?<=\.))\s*(?P<pub>[^.]{2,90}?),\s+(?P<year>\d{4})\.")
_DATE = re.compile(r"(?P<day>\d{1,2})\s+(?P<month>" + _MONTHS + r")\s+(?P<year>\d{4})")


def _plain_and_flags(tokens):
    """The entry's text, and for each character whether it is italic / in
    small caps."""
    plain, ital, sc = [], [], []
    for t in tokens:
        if t.get("fn") is not None:
            continue
        plain.append(t["t"])
        ital.extend([bool(t["i"])] * len(t["t"]))
        sc.extend([bool(t.get("sc"))] * len(t["t"]))
    return "".join(plain), ital, sc


def _italic_runs(ital, lo=0, hi=None):
    """[(start, end), ...] of italic text between lo and hi."""
    hi = len(ital) if hi is None else hi
    runs, i = [], lo
    while i < hi:
        if ital[i]:
            j = i
            while j < hi and ital[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    return runs


def _trim(plain, lo, hi, chars=" "):
    while lo < hi and plain[lo] in chars:
        lo += 1
    while hi > lo and plain[hi - 1] in chars:
        hi -= 1
    return lo, hi


def _author_end(plain, ital, sc):
    """Where the names stop: the first ". " followed by a title."""
    for m in re.finditer(r"\.\s+", plain[:400]):
        j = m.end()
        if j < len(plain) and (plain[j] in "“\"‘" or ital[j]):
            return m.start(), j
    # fall back on the small caps
    last = max((i for i, f in enumerate(sc[:400]) if f), default=-1)
    if last >= 0:
        m = re.compile(r"[^.]*\.\s*").match(plain, last + 1)
        if m:
            end = plain.rfind(".", 0, m.end())
            return end, m.end()
        return last + 1, last + 1
    return None, 0


def _expand_lpage(fpage, lpage):
    """Chicago elides page ranges: "213-49" is 213 to 249."""
    if fpage.isdigit() and lpage.isdigit() and len(lpage) < len(fpage):
        return fpage[:len(fpage) - len(lpage)] + lpage
    return lpage


def analyze_bib_entry(html_str, section_head=""):
    """One Bibliography entry (editor HTML) -> analysis dict.

    The dict has the keys bcs_editor.analyze_ref returns, so the rest of the
    tool (citation confidence, the References tab) can treat it like any
    other reference, plus "spans": [(start, end, tag, attrs)] -- what to tag
    where in the printed text -- and the extra Bibliography fields."""
    from bcs_editor import html_to_tokens
    tokens = html_to_tokens(html_str)
    plain, ital, sc = _plain_and_flags(tokens)
    # Small caps (the authors) and special-character fonts are presentation.
    # Their text stays; the markup cannot sit inside <string-name> and the
    # galley puts the small caps back on the names itself.
    tokens = [dict(t, sc=False, style_type="", lang="", cite=None, fig=None)
              for t in tokens if t.get("fn") is None]
    kind = section_kind(section_head)

    a = {
        "tokens": tokens, "plain": plain, "bib": True, "section_kind": kind,
        "people": [], "person_group_type": "author", "etal": False,
        "author_text": "", "resolved_author_text": "", "body_start_tok": 0,
        "title_lo": None, "title_hi": None, "source_lo": None, "source_hi": None,
        "year": "", "month": "", "day": "", "volume": "", "issue": "",
        "fpage": "", "lpage": "", "elocation": "", "publisher": "", "doi": "",
        "urls": [], "comment": "", "ptype": "other", "collab": "",
        "editors": [], "size": "", "isbns": [], "series": "", "degree": "",
        "institution": "", "medium": "", "people_detail": [],
        "title_text": "", "source_text": "", "spans": [],
    }
    spans = a["spans"]

    # --- authors -------------------------------------------------------------
    a_end, body = _author_end(plain, ital, sc)
    if a_end:
        lo, hi = _trim(plain, 0, a_end)
        author_text = plain[lo:hi]
        a["author_text"] = a["resolved_author_text"] = author_text
        names_text = author_text
        m = _ROLE_TAIL.search(names_text)
        if m:
            role = _ROLE_GROUP.get(m.group(1).lower(), "")
            a["person_group_type"] = role or "author"
            r_lo = lo + m.start(1)
            r_hi = lo + m.end()
            while plain[r_hi - 1] == " ":
                r_hi -= 1
            spans.append((r_lo, r_hi, "role", ""))
            names_text = names_text[:m.start()]
        m = _ETAL.search(names_text)
        if m:
            a["etal"] = True
            names_text = names_text[:m.start()]
        if "," in names_text or " and " in names_text:
            people = read_names(names_text, lo)
            a["people_detail"] = people
            a["people"] = [canonical_name(p) for p in people]
        elif names_text.strip():
            # one word or an organisation ("Province of British Columbia")
            if len(names_text.split()) == 1:
                p = {"surname": names_text.strip(), "given": "",
                     "span": (lo, lo + len(names_text.strip())),
                     "sur_span": (lo, lo + len(names_text.strip())),
                     "given_span": None, "inverted": True}
                a["people_detail"] = [p]
                a["people"] = [(p["surname"], "")]
            elif a["person_group_type"] != "author" or all(sc[lo:lo + len(names_text.strip())]):
                # "Lyana Patrick, dir." -- one person, given name first
                people = read_names(names_text.strip(), lo, inverted_first=False)
                a["people_detail"] = people
                a["people"] = [canonical_name(p) for p in people]
            else:
                a["collab"] = names_text.strip()
                spans.append((lo, lo + len(names_text.strip()), "collab", ""))
        for p in a["people_detail"]:
            _tag_person(spans, p)
    else:
        body = 0

    # --- title ---------------------------------------------------------------
    i = body
    while i < len(plain) and plain[i] == " ":
        i += 1
    after_title = i
    if i < len(plain) and plain[i] in "“\"":
        close = plain.find("”" if plain[i] == "“" else "\"", i + 1)
        if close > i:
            t_lo, t_hi = i + 1, close
            # Chicago puts the closing full stop inside the quotes; it is
            # punctuation, not part of the title
            if plain[t_hi - 1] in ".,":
                t_hi -= 1
            a["title_lo"], a["title_hi"] = t_lo, t_hi
            a["title_text"] = plain[t_lo:t_hi]
            after_title = close + 1
    elif i < len(plain) and ital[i]:
        # a whole work: its italic title is the source. A number set in
        # roman inside it ("Challenging Racist ... 150 Years") does not end it.
        runs = _italic_runs(ital, i)
        run = runs[0]
        for nxt_run in runs[1:]:
            gap = plain[run[1]:nxt_run[0]]
            if len(gap) <= 8 and re.fullmatch(r"[\s\d–-]+", gap):
                run = (run[0], nxt_run[1])
            else:
                break
        a["source_lo"], a["source_hi"] = _trim(plain, *run, chars=" ")
        after_title = run[1]

    # --- the container -------------------------------------------------------
    ref_end = len(plain)
    m_doi = _DOI.search(plain, after_title)
    m_url = _URL.search(plain, after_title)
    if m_url:
        ref_end = m_url.start()

    in_book = False
    if a["title_lo"] is not None and a["source_lo"] is None:
        for r in _italic_runs(ital, after_title, ref_end):
            before = plain[after_title:r[0]]
            # skip an italic word inside a sentence that isn't the venue
            if before.strip(" .,;:”\"") and not re.search(
                    r"(?:^|[.”\"]\s*)\s*(?:In\s+)?$", before) and \
                    not re.search(r"\.\s*$", before):
                continue
            a["source_lo"], a["source_hi"] = _trim(plain, *r)
            in_book = bool(re.search(r"\bIn\s+$", before))
            break
    if a["source_lo"] is not None:
        a["source_text"] = plain[a["source_lo"]:a["source_hi"]]
    tail_lo = a["source_hi"] if a["source_hi"] and a["source_hi"] > after_title \
        else after_title

    # --- what kind of work ---------------------------------------------------
    jm = _JOURNAL.match(plain, tail_lo) if a["source_lo"] is not None \
        and a["title_lo"] is not None and not in_book else None
    tm = _THESIS.match(plain, after_title) if a["title_lo"] is not None \
        and a["source_lo"] is None else None
    if tm and not re.search(r"\d", tm.group("deg")):
        a["ptype"] = "thesis"
    elif in_book:
        a["ptype"] = "chapter"
    elif jm:
        a["ptype"] = "journal"
    elif kind == "audiovisual":
        a["ptype"] = "other"
    elif kind == "report":
        a["ptype"] = "report"
    elif a["title_lo"] is None and a["source_lo"] is not None:
        a["ptype"] = "book"
    elif kind:
        a["ptype"] = {"journal": "journal", "thesis": "thesis",
                      "book": "book"}.get(kind, "other")

    # --- fields --------------------------------------------------------------
    if a["ptype"] == "journal" and jm:
        _journal_fields(a, jm, spans)
    elif a["ptype"] == "journal":
        # "Findings, March 2022." -- no volume or parentheses
        years = list(re.finditer(r"\b(?:(" + _MONTHS + r")\s+)?(\d{4})\b",
                                 plain[tail_lo:ref_end]))
        if years:
            m = years[-1]
            a["year"] = m.group(2)
            spans.append((tail_lo + m.start(2), tail_lo + m.end(2), "year", ""))
            if m.group(1):
                a["month"] = m.group(1)
                spans.append((tail_lo + m.start(1), tail_lo + m.end(1), "month", ""))
    elif a["ptype"] == "thesis" and tm:
        a["degree"] = tm.group("deg")
        a["institution"] = tm.group("inst").strip()
        a["year"] = tm.group("year")
        spans.append((tm.start("inst"), tm.end("inst"), "publisher-name", ""))
        spans.append((tm.start("year"), tm.end("year"), "year", ""))
    else:
        _book_fields(a, plain, tail_lo, ref_end, spans)

    # --- DOI / URL -----------------------------------------------------------
    if m_doi:
        a["doi"] = m_doi.group(1)
        href = "https://doi.org/" + m_doi.group(1)
        spans.append((m_doi.start(), m_doi.end(), "ext-link",
                      f' ext-link-type="doi" xlink:href="{esc_attr(href)}"'))
    elif m_url:
        a["urls"].append(m_url.group(0))
        spans.append((m_url.start(), m_url.end(), "ext-link",
                      f' ext-link-type="uri" xlink:href="{esc_attr(m_url.group(0))}"'))

    # still no year: the last one printed before the link
    if not a["year"]:
        years = list(re.finditer(r"\b(1[6-9]\d{2}|20\d{2})\b", plain[tail_lo:ref_end]))
        if years:
            m = years[-1]
            a["year"] = m.group(1)
            spans.append((tail_lo + m.start(1), tail_lo + m.end(1), "year", ""))

    # the title and source go in last, so the field spans above can be
    # checked against them
    if a["title_lo"] is not None:
        el = "chapter-title" if a["ptype"] == "chapter" else "article-title"
        spans.append((a["title_lo"], a["title_hi"], el, ""))
    if a["source_lo"] is not None:
        spans.append((a["source_lo"], a["source_hi"], "source", ""))

    a["comment"] = _leftover(a, plain)
    return a


def _tag_person(spans, p):
    lo, hi = p["span"]
    spans.append((lo, hi, "string-name", ""))
    spans.append((p["sur_span"][0], p["sur_span"][1], "surname", ""))
    if p.get("given_span"):
        spans.append((p["given_span"][0], p["given_span"][1], "given-names", ""))


def _journal_fields(a, jm, spans):
    for key, el in (("vol", "volume"), ("iss", "issue"), ("month", "month"),
                    ("year", "year")):
        if jm.group(key):
            a[{"vol": "volume", "iss": "issue"}.get(key, key)] = jm.group(key)
            spans.append((jm.start(key), jm.end(key), el, ""))
    pages = jm.group("pages")
    if pages:
        lo = jm.start("pages")
        m = re.match(r"(\w+)[–-](\w+)$", pages)
        if m:
            a["fpage"], a["lpage"] = m.group(1), _expand_lpage(m.group(1), m.group(2))
            spans.append((lo, lo + len(m.group(1)), "fpage", ""))
            spans.append((lo + m.start(2), lo + m.end(2), "lpage", ""))
        else:
            # one number with no range is an article number, not a page
            a["elocation"] = pages
            spans.append((lo, lo + len(pages), "elocation-id", ""))


def _book_fields(a, plain, lo, hi, spans):
    """Chapters, books, reports, audiovisual: everything after the title."""
    text = plain[lo:hi]

    m = _EDITED.search(text)
    if m:
        n_lo = lo + m.start(2)
        people = read_names(m.group(2), n_lo, inverted_first=False)
        a["editors"] = people
        if people:
            spans.append((people[0]["span"][0], people[-1]["span"][1],
                          "person-group", ' person-group-type="editor"'))
            for p in people:
                _tag_person(spans, p)

    for m in _ISBN.finditer(text):
        a["isbns"].append((m.group(1), (m.group(2) or "").strip()))
        spans.append((lo + m.start(1), lo + m.end(1), "isbn", ""))
    m = _SIZE.search(text)
    if m:
        a["size"] = m.group(1)
        spans.append((lo + m.start(), lo + m.end(), "size", ' units="pages"'))

    # "15 February 2025." -- a broadcast date
    m_date = _DATE.search(text)
    # the publisher is the last "Something, 2025." before the extent/ISBN
    pubs = [m for m in _PUB_YEAR.finditer(text)
            if not _DATE.search(m.group(0))]
    if pubs:
        m = pubs[-1]
        pub = m.group("pub").strip()
        p_lo = lo + m.start("pub") + (len(m.group("pub")) - len(m.group("pub").lstrip()))
        # older issues give the place first: "Tucson: University of Arizona Press"
        pm = re.match(r"([A-Z][^:;\d]{1,30}):\s+(.+)$", pub)
        if pm and ";" not in pub:
            a["publisher_loc"] = pm.group(1)
            spans.append((p_lo, p_lo + len(pm.group(1)), "publisher-loc", ""))
            p_lo += pm.start(2)
            pub = pm.group(2)
        a["publisher"] = pub
        a["year"] = m.group("year")
        spans.append((p_lo, p_lo + len(pub), "publisher-name", ""))
        spans.append((lo + m.start("year"), lo + m.end("year"), "year", ""))
        # the sentence before the publisher, if it isn't the editors or a
        # medium, is the series: "Land Management Handbook 78."
        before = text[:m.start("pub")].rstrip()
        sentences = [s for s in re.split(r"(?<!\b[A-Z]\.)(?<=\.)\s+", before)
                     if s.strip()]
        if sentences:
            last = sentences[-1].rstrip(".").strip()
            last_lo = lo + before.rfind(last) if last else -1
            if last and last_lo >= 0 and not re.match(
                    r"^[,\s]*(?:edited|translated|compiled|In\b)", last, re.I) \
                    and not last.startswith(("“", "\"")) \
                    and last_lo >= (a["source_hi"] or 0) \
                    and not any(s[2] == "person-group" and s[0] < last_lo + len(last)
                                and s[1] > last_lo for s in spans):
                a["series"] = last
                spans.append((last_lo, last_lo + len(last), "series", ""))
    elif m_date:
        a["year"], a["month"], a["day"] = (m_date.group("year"),
                                            m_date.group("month"),
                                            m_date.group("day"))
        for key in ("day", "month", "year"):
            spans.append((lo + m_date.start(key), lo + m_date.end(key), key, ""))

    # an episode or part title in quotes after the work's own title
    if a["title_lo"] is None:
        m = re.search(r"“([^”]+?)[.,]?”", text)
        if m:
            a["title_lo"], a["title_hi"] = lo + m.start(1), lo + m.end(1)
            a["title_text"] = m.group(1)
    m = re.match(r"\s*\.?\s*(Podcast|Film|Video|Documentary|Radio broadcast|"
                 r"Television broadcast|Sound recording)\b", text)
    if m:
        a["medium"] = m.group(1)


def _leftover(a, plain):
    """Printed text no field accounts for (binding, the medium, "Episode 96"),
    for the element-citation's <comment>."""
    used = [False] * len(plain)
    for lo, hi, tag, _ in a["spans"]:
        for k in range(max(lo, 0), min(hi, len(plain))):
            used[k] = True
    rest = "".join(ch if not used[k] else " " for k, ch in enumerate(plain))
    rest = re.sub(r"\b(?:In|edited by|translated by|pp\.|no\.|and|et al\.?)(?!\w)",
                  " ", rest)
    rest = re.sub(r"\((?:hc|pbk|cloth|paper|ebook|pb)\)", " ", rest)
    rest = re.sub(r"[“”\"‘’():,;.–—-]+", " ", rest)
    rest = " ".join(rest.split())
    return rest if re.search(r"[A-Za-z]{3}", rest) else ""


# =============================================================================
# 4. WRITING IT OUT
# =============================================================================

def _nest_ok(spans):
    """Drop any span that would cross another one (a misread; better an
    untagged field than malformed XML). Returns spans sorted for writing:
    by start, the wider first."""
    keep = []
    for s in sorted(spans, key=lambda s: (s[0], -s[1])):
        lo, hi = s[0], s[1]
        if hi <= lo:
            continue
        if any(k[0] < lo < k[1] < hi or lo < k[0] < hi < k[1] for k in keep):
            continue
        if any(k[0] == lo and k[1] == hi and k[2] == s[2] for k in keep):
            continue
        keep.append(s)
    return sorted(keep, key=lambda s: (s[0], -s[1]))


def _split_tokens(tokens, cuts):
    """Split tokens so every offset in cuts falls on a token boundary.
    Returns [(start, end, token), ...]."""
    out, pos = [], 0
    cuts = sorted(set(cuts))
    for t in tokens:
        text, start = t["t"], pos
        pieces = [c - start for c in cuts if start < c < start + len(text)]
        prev = 0
        for p in pieces + [len(text)]:
            if p > prev:
                nt = dict(t)
                nt["t"] = text[prev:p]
                out.append((start + prev, start + p, nt))
            prev = p
        pos += len(text)
    return out


# inside these, no formatting or other markup may appear
_TEXT_ONLY = {"surname", "given-names", "year", "month", "day", "volume",
              "issue", "fpage", "lpage", "elocation-id", "isbn", "collab",
              "publisher-name", "publisher-loc", "ext-link", "size", "role"}


def build_bib_mixed_citation(a):
    """The printed entry with its fields tagged."""
    from bcs_editor import tokens_to_jats
    spans = _nest_ok(a["spans"])
    pieces = _split_tokens(a["tokens"], [s[0] for s in spans] + [s[1] for s in spans])
    out, stack, run = [], [], []
    nxt = 0                                   # next span to open

    def flush():
        if run:
            if any(s[2] in _TEXT_ONLY for s in stack):
                out.append(esc("".join(t["t"] for t in run)))
            else:
                out.append(tokens_to_jats(run))
            run.clear()

    end_of_text = len(a["plain"])
    for start, _end, tok in pieces + [(end_of_text, end_of_text, None)]:
        while stack and stack[-1][1] <= start:
            flush()
            out.append(f"</{stack.pop()[2]}>")
        while nxt < len(spans) and spans[nxt][0] <= start:
            s = spans[nxt]
            nxt += 1
            if s[0] < start or s[0] >= end_of_text:
                continue                      # cannot happen after splitting
            flush()
            out.append(f"<{s[2]}{s[3]}>")
            stack.append(s)
        if tok is not None:
            run.append(tok)
    flush()
    while stack:
        out.append(f"</{stack.pop()[2]}>")
    return (f'<mixed-citation publication-type="{esc_attr(a["ptype"])}">'
            + "".join(out) + "</mixed-citation>")


def build_bib_element_citation(a):
    """The same entry as structured fields."""
    el = []

    def names_xml(people):
        out = []
        for sur, giv in people:
            out.append(f"<name><surname>{esc(sur)}</surname>"
                       + (f"<given-names>{esc(giv)}</given-names>" if giv else "")
                       + "</name>")
        return "".join(out)

    if a["people"]:
        pgt = a["person_group_type"]
        attrs = (f' person-group-type="{pgt}"' if pgt != "host"
                 else ' person-group-type="custom" custom-type="host"')
        el.append(f"<person-group{attrs}>{names_xml(a['people'])}"
                  + ("<etal/>" if a["etal"] else "") + "</person-group>")
    elif a["collab"]:
        el.append(f'<person-group person-group-type="author"><collab>'
                  f'{esc(a["collab"])}</collab></person-group>')

    def sub(lo, hi):
        from bcs_editor import tokens_to_jats as tj
        toks = [t for s, e, t in _split_tokens(a["tokens"], [lo, hi])
                if s >= lo and e <= hi]
        return tj(toks).strip()

    if a["title_lo"] is not None:
        t_el = "chapter-title" if a["ptype"] == "chapter" else "article-title"
        el.append(f"<{t_el}>{sub(a['title_lo'], a['title_hi'])}</{t_el}>")
    if a["source_lo"] is not None:
        el.append(f"<source>{esc(a['source_text'])}</source>")
    if a["editors"]:
        el.append('<person-group person-group-type="editor">'
                  + names_xml([canonical_name(p) for p in a["editors"]])
                  + "</person-group>")
    if a["series"]:
        el.append(f"<series>{esc(a['series'])}</series>")
    if a["ptype"] == "thesis" and a["institution"]:
        el.append(f"<publisher-name>{esc(a['institution'])}</publisher-name>")
    elif a["publisher"]:
        el.append(f"<publisher-name>{esc(a['publisher'])}</publisher-name>")
        if a.get("publisher_loc"):
            el.append(f"<publisher-loc>{esc(a['publisher_loc'])}</publisher-loc>")
    for key in ("year", "month", "day", "volume", "issue", "fpage", "lpage"):
        if a.get(key):
            el.append(f"<{key}>{esc(a[key])}</{key}>")
    if a["elocation"]:
        el.append(f"<elocation-id>{esc(a['elocation'])}</elocation-id>")
    if a["size"]:
        el.append(f'<size units="pages">{esc(a["size"])}</size>')
    for isbn, binding in a["isbns"]:
        el.append(f"<isbn>{esc(isbn)}</isbn>")
    if a["doi"]:
        el.append(f'<pub-id pub-id-type="doi">{esc(a["doi"])}</pub-id>')
    for url in a["urls"]:
        el.append(f'<ext-link ext-link-type="uri" xlink:href="{esc_attr(url)}">'
                  f"{esc(url)}</ext-link>")
    notes = []
    if a["degree"]:
        notes.append(f"{a['degree']} thesis")
    for isbn, binding in a["isbns"]:
        if binding:
            notes.append(f"ISBN {isbn} ({binding})")
    if a["comment"] and not a["degree"]:
        notes.append(a["comment"])
    if notes:
        el.append(f"<comment>{esc('; '.join(notes))}</comment>")
    return (f'<element-citation publication-type="{esc_attr(a["ptype"])}">'
            + "".join(el) + "</element-citation>")


def confidence(a):
    """0-3, as the References tab shows it for other entries: has a year,
    has a title, has authors."""
    return sum([bool(a["year"]),
                a["title_lo"] is not None or a["source_lo"] is not None,
                bool(a["people"] or a["collab"])])


# =============================================================================
# 5. OLDER DRAFTS
# =============================================================================

def _sort_key(entry_plain):
    return re.sub(r"[^a-z]", "", entry_plain.lower())[:12]


def regroup_old_draft(project):
    """Drafts imported before this module existed have the section heads as
    empty headings in the Body tab and every entry in one list. Each section
    is alphabetical, so a new section starts wherever the alphabet starts
    over: split there, and give each list its head back -- but only when the
    number of restarts matches the number of heads, otherwise leave the
    draft alone and say so.

    Returns True if the draft was changed."""
    if not project.get("bibliography"):
        return False
    groups = project.get("ref_groups") or []
    blocks = project.get("blocks") or []
    heads = [b for b in blocks if b.get("kind") == "heading"]
    if len(groups) != 1 or not heads or len(heads) != len(blocks):
        return False
    refs = groups[0].get("refs") or []

    def plain(r):
        return re.sub(r"<[^>]+>", "", html.unescape(r.get("html") or ""))

    starts = [0] + [i for i in range(1, len(refs))
                    if _sort_key(plain(refs[i])) < _sort_key(plain(refs[i - 1]))]
    titles = [" ".join(re.sub(r"<[^>]+>", "", html.unescape(h.get("html") or "")).split())
              for h in heads]
    if len(starts) != len(titles):
        msg = ("This Bibliography draft was imported before the tool knew about "
               "Bibliography sections, and its entries could not be sorted into "
               "them automatically. Re-import the issue, or use \"Split list here\" "
               "in the References tab.")
        if msg not in project.setdefault("warnings", []):
            project["warnings"].append(msg)
        return False
    from bcs_idml import bib_heading_title
    new = []
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(refs)
        new.append({"title": bib_heading_title(titles[k]), "refs": refs[s:e]})
    project["ref_groups"] = new
    project["blocks"] = []
    return True
