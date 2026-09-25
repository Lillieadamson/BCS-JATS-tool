# bcs_crossref.py
"""Ask Crossref for the DOI of a reference-list entry.

app.py asks this for suggestions, and you accept or dismiss them in the
References tab. Accepting one appends the DOI to the entry's text. The
existing parser then picks it up as <pub-id pub-id-type="doi"> in the
<element-citation> and as a linked DOI in the <mixed-citation>, so nothing
downstream needs to change.

BC Studies is Chicago author-date, so analyze_ref() reads the year between
the author and the title. That only affects the parsing; the scoring below
compares whatever analyze_ref() found against what Crossref returns.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher

from bcs_editor import analyze_ref

try:
    from bcs_config import CROSSREF_MAILTO
except ImportError:      # older config file
    CROSSREF_MAILTO = "info@bcstudies.ubc.ca"

API = "https://api.crossref.org/works"
ROWS = 5
TIMEOUT = 25


STRONG = 0.86           # confident enough to offer "accept" plainly
WEAK = 0.64             # offered, but flagged as needing a look
MIN_TITLE = 0.55        # below this the candidate is not the same work

# seconds between calls. Crossref hands out 429s fast on the anonymous
# pool; setting CROSSREF_MAILTO gets us the polite pool and lets us hurry
MIN_GAP = 0.4 if CROSSREF_MAILTO else 1.1
RETRIES = 3
_last_call = [0.0]

# these things never have DOIs and match badly against journal articles
_JUNK_TITLES = {"ibid", "op cit", "n p", "np"}


# ---------------------------------------------------------------- text helpers

def _norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return " ".join(s.split())


def _ratio(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _tok_text(a, lo, hi):
    if lo is None:
        return ""
    return " ".join("".join(t["t"] for t in a["tokens"][lo:hi]).split()).strip(" .,;:“”\"")


def _our_title(a):
    """The work's own title if the entry has one, else the italic whole-work title."""
    t = _tok_text(a, a["title_lo"], a["title_hi"])
    return t or _tok_text(a, a["source_lo"], a["source_hi"])


def _our_container(a):
    if a["title_lo"] is None:
        return ""      # the italics were the work itself not a container
    return _tok_text(a, a["source_lo"], a["source_hi"])


def _surnames(a):
    return {_norm(s) for s, _g in a["people"] if _norm(s)}


# ---------------------------------------------------------------- API call

def _get(url):
    ua = "bcs-jats-tool/1.0 (JATS conversion for BC Studies)"
    if CROSSREF_MAILTO:
        ua += f" mailto:{CROSSREF_MAILTO}"
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    delay = 2.0
    for attempt in range(RETRIES):
        wait = MIN_GAP - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            # 429 = we are going too fast, 5xx = their end, both worth retrying
            if e.code not in (429, 500, 502, 503, 504) or attempt == RETRIES - 1:
                raise
            try:
                delay = max(delay, float(e.headers.get("Retry-After") or 0))
            except ValueError:
                pass
            time.sleep(delay)
            delay *= 2
    return {}


def _search(a):
    """One bibliographic query built from the printed entry."""
    query = re.sub(r"https?://\S+", " ", a["plain"])
    query = re.sub(r"\bdoi:\s*\S+", " ", query, flags=re.IGNORECASE)
    query = " ".join(query.split())[:350]
    if len(query) < 12:
        return []
    params = {
        "query.bibliographic": query,
        "rows": str(ROWS),
        "select": "DOI,title,subtitle,author,container-title,issued,type,publisher,volume,issue,page,URL",
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO
    data = _get(API + "?" + urllib.parse.urlencode(params))
    return (data.get("message") or {}).get("items") or []


# ---------------------------------------------------------------- the scoring

def _cand_title(item):
    t = (item.get("title") or [""])[0] or ""
    sub = (item.get("subtitle") or [""])[0] or ""
    return t, (f"{t}: {sub}" if sub else t)


def _cand_year(item):
    try:
        return int(item["issued"]["date-parts"][0][0])
    except Exception:
        return None


def _cand_surnames(item):
    out = set()
    for p in item.get("author") or []:
        fam = _norm(p.get("family") or "")
        if fam:
            out.add(fam)
    return out


def _score(a, item):
    """0..1, plus the reasons, so the UI can say why it thinks this is the one."""
    our_title = _our_title(a)
    if _norm(our_title) in _JUNK_TITLES:
        return 0.0, {}
    bare, with_sub = _cand_title(item)
    t = max(_ratio(our_title, bare), _ratio(our_title, with_sub))
    if t < MIN_TITLE:
        return 0.0, {}

    ours, theirs = _surnames(a), _cand_surnames(item)
    author_hit = bool(ours & theirs)
    our_year = int(a["year"]) if a["year"].isdigit() else None
    their_year = _cand_year(item)
    year_hit = bool(our_year and their_year and abs(our_year - their_year) <= 1)
    our_cont = _our_container(a)
    cont = (item.get("container-title") or [""])[0] or ""
    cont_ratio = _ratio(our_cont, cont) if (our_cont and cont) else None
    cont_hit = bool(cont_ratio is not None and cont_ratio > 0.8)

    score = t
    if author_hit:
        score += 0.12
    elif ours and theirs:
        score -= 0.16
    if year_hit:
        score += 0.06
    elif our_year and their_year:
        score -= 0.09
    if cont_hit:
        score += 0.06
    elif cont_ratio is not None and cont_ratio < 0.5:
        score -= 0.15          # printed in a different journal so not this one

    # a journal article that came back as a book is usually a title collision
    if a["ptype"] == "journal" and not cont_hit and \
            (item.get("type") or "").startswith(("book", "monograph", "edited")):
        score -= 0.10
    # and a book that came back as a journal article is nearly always a
    # review of that book, which carries the book's title and author
    if a["ptype"] == "book" and (item.get("type") or "") == "journal-article":
        score -= 0.40

    # a short generic title on its own proves nothing
    if len(_norm(our_title).split()) < 3 and not author_hit:
        score -= 0.25

    why = {"title": round(t, 3), "author": author_hit, "year": year_hit,
           "container": cont_hit,
           # title agreement alone isn't enough to call a match
           "corroborated": bool(author_hit or year_hit or cont_hit)}
    return max(0.0, min(1.0, score)), why


def _describe(item, why):
    bare, _ = _cand_title(item)
    people = item.get("author") or []
    names = ", ".join(
        " ".join(x for x in [p.get("given"), p.get("family")] if x) or (p.get("name") or "")
        for p in people[:4])
    if len(people) > 4:
        names += ", et al."
    bits = []
    if why.get("author"):
        bits.append("author matches")
    if why.get("year"):
        bits.append("year matches")
    if why.get("container"):
        bits.append("journal matches")
    bits.append(f"title {int(round(why.get('title', 0) * 100))}%")
    import html as _h
    return {
        "doi": item.get("DOI", ""),
        "title": _h.unescape(bare),
        "authors": names,
        "container": _h.unescape((item.get("container-title") or [""])[0] or item.get("publisher", "")),
        "year": _cand_year(item) or "",
        "type": (item.get("type") or "").replace("-", " "),
        "why": ", ".join(bits),
    }


# ---------------------------------------------------------------- entry points

def lookup_entry(html, prev_author_text=""):
    """One reference entry -> a suggestion dict for the References tab."""
    a = analyze_ref(html or "", prev_author_text)
    result = {"status": "none", "resolved_author": a["resolved_author_text"]}
    if not a["plain"].strip():
        result["status"] = "empty"
        return result
    if a["doi"]:
        result["status"] = "has_doi"
        result["doi"] = a["doi"]
        return result
    try:
        items = _search(a)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        result["status"] = "error"
        result["message"] = f"Crossref unreachable ({e})"
        return result
    except Exception as e:
        result["status"] = "error"
        result["message"] = str(e)
        return result

    best, best_score, best_why = None, 0.0, {}
    for item in items:
        s, why = _score(a, item)
        if s > best_score:
            best, best_score, best_why = item, s, why
    if not best or best_score < WEAK:
        return result
    result.update(_describe(best, best_why))
    result["score"] = round(best_score, 3)
    result["status"] = ("strong" if best_score >= STRONG and best_why.get("corroborated")
                        else "weak")
    return result


def lookup_groups(ref_groups, ids):
    """Walk the lists in order (so repeat-author entries inherit the author
    above) and look up only the ids asked for."""
    wanted = set(ids or [])
    out = []
    for group in ref_groups or []:
        prev_author = ""
        for r in group.get("refs", []):
            rid = r.get("id") or ""
            if rid in wanted:
                res = lookup_entry(r.get("html", ""), prev_author)
                prev_author = res.pop("resolved_author", "") or prev_author
                res["id"] = rid
                out.append(res)
            else:
                try:
                    prev_author = analyze_ref(r.get("html", ""), prev_author)["resolved_author_text"]
                except Exception:
                    pass
    return out


def format_doi_suffix(doi):
    """How an accepted DOI is written into the entry text (Chicago style)."""
    doi = re.sub(r"^\s*(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", (doi or "").strip(), flags=re.I)
    doi = doi.rstrip(" .,;")
    return f"https://doi.org/{doi}." if doi else ""


# ---------------------------------------------------------------- footnotes
#
# Most BC Studies articles cite in Chicago notes rather than author-date, so
# the full citations live inside the notes, often several to a note and mixed
# in with commentary:
#
#   See Linda Gordon, “The Perils of Innocence,” <i>Journal of the History of
#   Childhood and Youth</i> 1, no. 3 (2008): 331–50; Milloy, <i>A National
#   Crime</i>, 68–92.
#
# A note is cut into citation-sized pieces at semicolons and sentence ends.
# A piece is looked up only if it looks like a first, full citation: a quoted
# or italic title and a year. Short forms ("Milloy, A National Crime, 68") and
# "Ibid." have no year, so they are never sent. An accepted DOI goes at the
# end of its own citation, before the ";" or "." that closes it, the way
# Chicago notes print it: "…(2008): 331–50, https://doi.org/10.1353/hcy.0.0021."

from bcs_editor import (html_to_tokens, tokens_plain, _resplit_quotes,  # noqa: E402
                        QUOTE_CHARS, YEAR_RE, DOI_RE)
from bcs_names import split_byline  # noqa: E402

# a full stop after one of these does not end a citation
_ABBREV = {"ed", "eds", "no", "nos", "vol", "vols", "trans", "st", "dr", "mr",
           "mrs", "ms", "ch", "chap", "pp", "p", "n", "nn", "repr", "rev",
           "esp", "cf", "ibid", "et", "al", "jr", "sr", "co", "inc", "ltd",
           "dept", "univ", "comp", "pt", "sec", "fig", "e.g", "i.e", "vs", "v"}

# lead-ins that sit between a note's commentary and the citation's author
_LEAD_IN = re.compile(
    r"^.*?\b(?:see(?:\s+also)?|cf\.|compare|include[sd]?|including|e\.g\.,?|"
    r"quoted\s+in|cited\s+in|discussed\s+in|argues\s+in|in)\s+(?=[A-Z])", re.S)


def _segments(plain):
    """(lo, hi) character spans of the citation-sized pieces of a note. hi
    stops before the ";" or "." that closes the piece."""
    spans, lo, depth, in_q = [], 0, 0, False
    for i, ch in enumerate(plain):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "“":
            in_q = True
        elif ch == "”":
            in_q = False
        if depth or in_q:
            continue
        if ch == ";":
            spans.append((lo, i))
            lo = i + 1
        elif ch == "." and re.match(r"\s+[A-Z“‘(]", plain[i + 1:i + 3] or ""):
            word = re.search(r"([\w.]+)$", plain[lo:i])
            word = (word.group(1) if word else "").lower()
            if word in _ABBREV or re.fullmatch(r"[a-z]", word) or \
                    re.search(r"\b[A-Z]$", plain[lo:i]):   # an initial: "J.R. Miller"
                continue
            spans.append((lo, i))
            lo = i + 1
    tail = plain[lo:].rstrip()
    if tail.endswith("."):
        tail = tail[:-1]
    spans.append((lo, lo + len(tail)))
    return [(a, b) for a, b in spans if plain[a:b].strip()]


def _analyze_note_piece(tokens, plain):
    """A Chicago note citation -> the same dict shape analyze_ref() returns,
    as far as _score() needs it. None if it is not a full citation."""
    if not YEAR_RE.search(plain) or DOI_RE.search(plain):
        return None
    a = {"tokens": tokens, "plain": plain, "people": [], "title_lo": None,
         "title_hi": None, "source_lo": None, "source_hi": None,
         "year": "", "ptype": "other", "doi": ""}
    qpos = [i for i, t in enumerate(tokens) if t["t"] in QUOTE_CHARS]
    first_ital = next((i for i, t in enumerate(tokens) if t["i"] and t["t"].strip()), None)
    if len(qpos) >= 2 and (first_ital is None or qpos[0] < first_ital):
        a["title_lo"], a["title_hi"] = qpos[0] + 1, qpos[1]
    start = a["title_hi"] + 1 if a["title_hi"] is not None else 0
    for i in range(start, len(tokens)):
        if tokens[i]["i"] and tokens[i]["t"].strip():
            hi = i
            while hi < len(tokens) and tokens[hi]["i"]:
                hi += 1
            a["source_lo"], a["source_hi"] = i, hi
            break
    if a["title_lo"] is None and a["source_lo"] is None:
        return None
    first = a["title_lo"] - 1 if a["title_lo"] is not None else a["source_lo"]
    title_at = len(tokens_plain(tokens[:first]))
    after = plain[title_at:]
    # the publication year: the first one after the title, in brackets if any
    m = re.search(r"\([^)]*?\b(1[5-9]\d{2}|20\d{2})\b[^)]*\)", after) or YEAR_RE.search(after)
    if not m:
        return None
    a["year"] = m.group(1)
    if a["title_lo"] is not None and a["source_lo"] is not None:
        between = tokens_plain(tokens[a["title_hi"]:a["source_lo"]])
        a["ptype"] = "chapter" if re.search(r"\bin\s*$", between) else "journal"
    else:
        a["ptype"] = "book"
    # the author is what sits just before the title, minus any lead-in
    who = _LEAD_IN.sub("", plain[:title_at]).strip(" ,.:")
    who = re.sub(r",?\s*\beds?\.?$", "", who).strip(" ,")
    if who and len(who) <= 90 and not re.search(r"\b(?:the|of|this|that|is|was)\b", who):
        try:
            a["people"] = split_byline(who)
        except Exception:
            a["people"] = []
    return a


def lookup_note_part(html):
    """One note paragraph -> a suggestion per full citation in it. "at" is
    the plain-text offset where the DOI goes and "drop" how many characters
    it replaces there (a URL it stands in for, else 0); the editor does the
    edit, so that accepting one suggestion can shift the others along."""
    tokens = _resplit_quotes(html_to_tokens(html or ""))
    plain = tokens_plain(tokens)
    out = []
    for lo, hi in _segments(plain):
        # the piece's own tokens, cut at its character edges
        piece, run = [], 0
        for t in tokens:
            nxt = run + len(t["t"])
            if nxt > lo and run < hi and t["fn"] is None:
                nt = dict(t)
                nt["t"] = t["t"][max(lo - run, 0):hi - run]
                piece.append(nt)
            run = nxt
        text = tokens_plain(piece)
        a = _analyze_note_piece(piece, text)
        if a is None or _norm(_our_title(a)) in _JUNK_TITLES:
            continue
        res = {"cite": " ".join(text.split()), "status": "none"}
        try:
            items = _search(a)
        except Exception as e:
            res.update(status="error", message=f"Crossref unreachable ({e})")
            out.append(res)
            continue
        best, best_score, best_why = None, 0.0, {}
        for item in items:
            s, why = _score(a, item)
            if s > best_score:
                best, best_score, best_why = item, s, why
        if best and best_score >= WEAK:
            res.update(_describe(best, best_why))
            res["score"] = round(best_score, 3)
            res["status"] = ("strong" if best_score >= STRONG and best_why.get("corroborated")
                             else "weak")
            res["at"], res["drop"] = hi, 0
            # Chicago: a DOI is cited instead of a URL, so a citation that
            # ends in an ordinary link has the link swapped for the DOI
            m = re.search(r"https?://\S+$", text.rstrip())
            if m:
                res["at"], res["drop"] = lo + m.start(), m.end() - m.start()
                res["replaces"] = m.group(0)
        out.append(res)
    return out


def lookup_notes(notes, wanted):
    """wanted: [[note index, part index], ...] -> one result per part."""
    out = []
    for ni, pi in wanted or []:
        try:
            part = notes[ni]["parts"][pi]
        except (IndexError, KeyError, TypeError):
            continue
        out.append({"note": ni, "part": pi, "html": part.get("html", ""),
                    "hits": lookup_note_part(part.get("html", ""))})
    return out
