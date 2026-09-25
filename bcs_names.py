#!/usr/bin/env python3
"""
bcs_names.py -- turning a printed byline or reference into people.

Split out of the parser because two different callers need it: the byline
on an article and the author field of a reference

CHICAGO BOTH FLAVOURS
----------------------
Author-date reference list:

    Harris, Douglas C. 2008. Landing Native Fisheries...
    Brandes, Oliver M., Rosie Simms, and Deborah Curran. 2020. ...

Notes-bibliography footnote:

    Douglas C. Harris, Landing Native Fisheries (Vancouver: UBC Press, 2008).

So the first author may be inverted or not, and everyone after the first is
printed given-name-first in both. The one real ambiguity is a lone "Smith,
John" versus "Smith, John, and Jane Doe" -- both start the same way, which is
why the first chunk is handled separately below.
"""

import re

_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# Things that follow a name but are not part of it.
_ROLE_TAIL = re.compile(
    r",?\s*\b(ed|eds|editor|editors|trans|translator|translators|comp|"
    r"compiler|compilers|dir|director|directors)\.?\s*$", re.I)


def split_authors(author_text):
    """A printed author string -> [(surname, given), ...], best effort.

    Handles: an inverted first author, given-first authors after it, three or
    more names, an ampersand, a generational suffix, an editor/director role
    label, and a parenthetical identity or affiliation note ("Dallas Hunt
    (Cree)"), which is dropped because it is not part of the name."""
    text = " ".join((author_text or "").split()).strip().rstrip(".")
    text = re.sub(r"\s*\([^)]*\)", "", text).strip().rstrip(",").strip()
    text = _ROLE_TAIL.sub("", text).strip().rstrip(",")
    # "prepared by David Gill, mlis" -- the Bibliography's byline.
    text = re.sub(r"^\s*(prepared|compiled|edited)\s+by\s+", "", text, flags=re.I)
    if not text:
        return []

    parts = re.split(r",\s*and\s+|\s+and\s+|\s*&\s*|\s*;\s*", text)
    people = []

    def is_suffix(t):
        return t.rstrip(".").lower() in _NAME_SUFFIXES

    def given_surname(t):
        bits = t.split()
        if len(bits) >= 2:
            people.append((bits[-1], " ".join(bits[:-1])))
        elif bits:
            people.append((bits[0], ""))

    for i, part in enumerate(parts):
        part = part.strip().strip(",").strip()
        if not part:
            continue
        if is_suffix(part) and people:
            sur, giv = people[-1]
            people[-1] = (sur, (giv + " " + part).strip())
            continue
        if i == 0 and "," in part:
            # An inverted first author, possibly followed by more authors in
            # the same comma-separated chunk:
            #   "Brandes, Oliver M., Rosie Simms"
            chunks = [c.strip() for c in part.split(",") if c.strip()]
            people.append((chunks[0], chunks[1] if len(chunks) > 1 else ""))
            for extra in chunks[2:]:
                if is_suffix(extra):
                    sur, giv = people[-1]
                    people[-1] = (sur, (giv + " " + extra).strip())
                else:
                    given_surname(extra)
        else:
            given_surname(part)
    return people


def split_byline(byline):
    """An article byline, which is always printed given-name-first, and often
    carries a footnote dagger or an asterisk that InDesign put there."""
    text = re.sub(r"[\*†‡]+", "", byline or "")
    text = re.sub(r"\s*\([^)]*\)", "", text)
    parts = re.split(r",\s*and\s+|\s+and\s+|\s*&\s*|,\s*", text)
    people = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.rstrip(".").lower() in _NAME_SUFFIXES and people:
            sur, giv = people[-1]
            people[-1] = (sur, (giv + " " + part).strip())
            continue
        bits = part.split()
        if len(bits) >= 2:
            people.append((bits[-1], " ".join(bits[:-1])))
        elif bits:
            people.append((bits[0], ""))
    return people
