#!/usr/bin/env python3
"""
bcs_styles.py -- if BC Studies renames a style, or adds one,
this is the file to change.

STYLE PATHS
-----------
IDML stores a style as `Group%3aLeaf`, escaping a literal colon inside a name
as `\\%3a`. `Article%3aA\\%3aArticle\\%3aTITLE` is the style `A:Article:TITLE`
in the group `Article`. `decode_style_path` turns that back into the path
`Article:A:Article:TITLE`, and every key below is written in that form.

WHAT A KIND MEANS
-----------------
The kinds are the tool's semantic vocabulary -- the same short list the DOCX
parser collapsed thirty Word styles into. Thirty presentational labels in,
about twenty semantic categories out, and from there the JATS is mechanical.
"""

import re

# =============================================================================
# 1. DECODING
# =============================================================================

_ESCAPED = re.compile(r"\\%([0-9A-Fa-f]{2})")
_SEP = re.compile(r"%3a", re.IGNORECASE)


def decode_style_path(raw):
    """`Article%3aA\\%3aArticle\\%3aTITLE` -> `Article:A:Article:TITLE`.

    Unescaped `%3a` is the group separator; `\\%3a` is a colon inside a name.
    Both end up as ':' in the decoded path, which is lossy but harmless: no two
    BC Studies styles differ only in where their colons are escaped."""
    if not raw:
        return ""
    s = _ESCAPED.sub(lambda m: chr(int(m.group(1), 16)), raw)
    s = _SEP.sub(":", s)
    s = s.replace("\\", "")
    return s.strip()


# =============================================================================
# 2. THE VOCABULARY
# =============================================================================
#
# Keys are decoded style paths. Values are kinds. A style not listed here is
# reported as unmapped 

STYLE_MAP = {
    # -- Articles ------------------------------------------------------------
    "Article:A:Article:TITLE":            "title",
    "Article:A:Article:SUBTITLE":         "subtitle",
    "Article:A:Article:AUTHOR":           "byline",
    "Article:A:Article:AUTHOR (Article)": "byline",
    "A:Article:AUTHOR (Article)":         "byline",
    "Article:A:Article:Text1stPara":      "p",
    "Article:A:Article:Text":             "p",
    "Article:A:Article:SubHeadOne":       "heading",
    "Article:A:Article:SubHeadTwo":       "heading2",
    "Article:A:Article:SubHeadThree":     "heading3",
    "Article:A:Article:TextQUOTE":        "blockquote",
    "Article:A:ArticleTextQUOTE":         "blockquote",
    "Article:A:Article:Footnote Text":    "note",
    "Article:A:Article:References":       "reference",
    "Article:A:Article:FigureCaption":    "fig-caption",
    "Article:A:Article:TextListBullet":   "list-bullet",
    "Article:A:Article:TextListNumbered": "list-numbered",
    "Article:A:Article:FIVE ASTERISKS":   "divider",
    "Article:Paragraph Style 1":          "p",

    # -- Book reviews --------------------------------------------------------
    "Book Review:B:BookReview:BookTitle":            "book-title",
    "Book Review:B:BookReview:BookAuthor":           "book-author",
    "Book Review:B:BookReview:BookInfo":             "book-info",
    "Book Review:B:BookReview:ReviewAuthor":         "reviewer",
    "Book Review:B:BookReview:ReviewAuthorLocation": "reviewer-affiliation",
    "Book Review:B:BookReviewTextFirstPara":         "p",
    "Book Review:B:BookReview:Text":                 "p",
    "Book Review:B:BookReview:SubHeadOne":           "heading",
    "Book Review:B:BookReview:WorksCited":           "works-cited",

    # -- Review essays -------------------------------------------------------
    "Review Essay:RE:ReviewEssay:Title":          "title",
    "Review Essay:RE:ReviewEssay:SubTitle":       "subtitle",
    "Review Essay:RE:ReviewEssay:Author":         "byline",
    "Review Essay:RE:ReviewEssay:1stBookTitle":   "book-title",
    "Review Essay:RE:ReviewEssay:BookTitle":      "book-title-following",
    "Review Essay:RE:ReviewEssay:BookAuthor":     "book-author",
    "Review Essay:RE:ReviewEssay:BookInfo":       "book-info",
    "Review Essay:RE:ReviewEssay:Text1stPara":    "p",
    "Review Essay:RE:ReviewEssay:Text":           "p",

    # -- Bibliography of British Columbia ------------------------------------
    "Bibliography:BIB:Bibliography": "bibliography",
    "Bibliography:BIB:SubHeadOne":   "heading",

    # -- Tables --------------------------------------------------------------
    "Tables:TABLE:TableName":   "table-title",
    "Tables:TABLE:TableNumber": "table-title",

    # -- Table of contents (read for section names, never rendered) ----------
    "Table of Contents:TOC:ArticleTitle":      "toc",
    "Table of Contents:TOC:ArticleAuthor":     "toc",
    "Table of Contents:TOC:BookTitle":         "toc",
    "Table of Contents:TOC:BookAuthor":        "toc",
    "Table of Contents:TOC:BookReviewer":      "toc",
    "Table of Contents:TOC:CatagoryHeading":   "toc",
    "Table of Contents:TOC:BCStudiesHeading":  "toc",

    # -- Word import leftovers ----------------------------------------------
    # These arrive when a contributor's Word styles survive placement. They
    # carry no BC Studies meaning, but they carry text, so they are mapped to
    # the least-wrong thing 
    "Normal":                   "p",
    "Body":                     "p",
    "Body Text":                "p",
    "Default":                  "p",
    "No Spacing":               "p",
    "Normal (Web)":             "p",
    "Normal first line indent": "p",
    "List Paragraph":           "p",
    "p1":                       "p",
    "Quote":                    "blockquote",
    "Block Text":               "blockquote",
    "Caption":                  "fig-caption",
    "Footnote text":            "note",
    "Footnote Text":            "note",
    "Annotation text":          "note",
    "Heading":                  "heading",
    "Heading 1":                "heading",
    "Heading 2":                "heading2",
    "Heading 3":                "heading3",
}

# Styles InDesign always has and which never carry journal content.
IGNORED_STYLES = {
    "$ID/NormalParagraphStyle",
    "$ID/[No paragraph style]",
}


# =============================================================================
# 3. STRUCTURE
# =============================================================================

# A style that opens a new piece.
BOUNDARY_STYLES = {
    "Article:A:Article:TITLE",
    "Review Essay:RE:ReviewEssay:Title",
    "Review Essay:RE:ReviewEssay:1stBookTitle",
    "Book Review:B:BookReview:BookTitle",
}

# A style that opens a new piece only when the current one already has content.
# In a review essay the second and later book titles are part of the same
# piece; in the book-review section every book title is a new review. The
# distinction is which style is used, which is why they are listed apart.
REVIEW_BOUNDARY_STYLES = set()

# Style group -> the issue section a piece from that group belongs to. The
# table of contents overrides this whenever it names a section explicitly.
SECTION_FOR_GROUP = {
    "Article":      "Articles",
    "Book Review":  "Book Reviews",
    "Review Essay": "Review Essays",
    "Bibliography": "Bibliography of British Columbia",
}

# Kinds that are body content (used by the parser's emptiness test).
ARTICLE_KINDS = {"p", "blockquote", "heading", "heading2", "heading3",
                 "divider", "fig-caption", "list-bullet", "list-numbered"}


def style_kind(path):
    """The semantic kind of a decoded style path, or None if unmapped."""
    if not path or path in IGNORED_STYLES:
        return None
    if path in STYLE_MAP:
        return STYLE_MAP[path]
    # Fall back to the leaf, so a style moved into a different group still
    # resolves. This is what makes the vocabulary survive an InDesign
    # reorganisation.
    leaf = path.rsplit(":", 1)[-1]
    for known, kind in STYLE_MAP.items():
        if known.rsplit(":", 1)[-1] == leaf:
            return kind
    return None


def known_styles():
    """Every style this tool recognises, for the pre-flight check."""
    return sorted(STYLE_MAP)
