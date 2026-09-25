# The BC Studies style vocabulary

*BC Studies*' InDesign paragraph styles are a controlled vocabulary for
encoding the journal. This document specifies it.

That framing is deliberate. A typesetter applying `B:BookReview:BookInfo` is
not choosing a font; they are asserting that the paragraph is the publishing
details of a book under review. The style name is the encoding. Everything the
tool does downstream depends on that assertion being made correctly and
consistently.

The machine-readable version of this document is `bcs_styles.py`. **If you
change one, change the other.**

---

## Why InDesign and not Word

The Canadian Literature version of this tool read Word, because Word was where
that journal's vocabulary lived. BC Studies' vocabulary lives in InDesign, and
the typeset file turns out to be the better source in four ways the Word file
cannot match:

| | Word (pre-layout) | IDML (typeset) |
|---|---|---|
| Page numbers | typed by hand | read from the frame-to-page map |
| Footnotes | a marker and a list at the end | anchored at the exact character |
| Figures | Word renames the media; filename lost | the linked graphic's real filename |
| Corrections | whatever the author sent | the state the issue went to press in |

There is a fifth, less obvious gain. A Word style that the parser did not
recognise used to import as a plain paragraph. IDML
declares its styles in the package, so the tool now checks them **before**
importing anything — see *Pre-flight* below.

---

## How style names are written

IDML stores a style as `Group%3aLeaf`, escaping a literal colon inside a name
as `\%3a`. So

```
Article%3aA\%3aArticle\%3aTITLE
```

is the style `A:Article:TITLE` in the style group `Article`.
`bcs_styles.decode_style_path` turns that back into the path

```
Article:A:Article:TITLE
```

and every key in `STYLE_MAP` is written that way. If a style is moved into a
different group in InDesign, the tool falls back to matching the leaf name, so
a reorganisation does not break the vocabulary.

---

## Boundary-signalling styles

These start a new piece. They are the answer to "how does it know when one
article stops and another starts?"

| Style | Effect |
|---|---|
| `Article:A:Article:TITLE` | Starts a new article; text becomes the title |
| `Review Essay:RE:ReviewEssay:Title` | Starts a new review essay |
| `Review Essay:RE:ReviewEssay:1stBookTitle` | Starts a review essay that has no title of its own |
| `Book Review:B:BookReview:BookTitle` | Starts a new book review |

> **This is the most fragile part of the system**, as it was in the Word
> version. A mis-styled title merges two pieces into one. It fails
> less often here only because InDesign styles are applied by one typesetter to
> a template, rather than by each contributor to their own manuscript.

There is one exception. BC Studies typesets a
**section divider** — "ARTICLES", "BOOK REVIEWS", "SOUNDWORKS", "THIS SPACE
HERE" — with the same `TITLE` style an article uses. The tool tells them apart
by the table of contents: a title that is also a category name in the TOC is a
divider, and sets the section for what follows instead of opening a piece. If
a divider is *also* the piece (as "THE FRONT" is, being both a heading and an
artist's statement), its name is carried forward and used to open the next
piece.

---

## Content-typing styles

| Style | Becomes |
|---|---|
| `Article:A:Article:SUBTITLE` | joined to the title |
| `Article:A:Article:AUTHOR` | byline |
| `Article:A:Article:Text1stPara` | `<p>` |
| `Article:A:Article:Text` | `<p>` |
| `Article:A:Article:SubHeadOne / Two / Three` | a real nested `<sec>` with `<title>`, at depth 1 / 2 / 3 |
| `Article:A:Article:TextQUOTE`, `Article:A:ArticleTextQUOTE` | `<disp-quote>` |
| `Article:A:Article:Footnote Text` | footnote text (normally reached inside a `<Footnote>`, not as a body paragraph) |
| `Article:A:Article:References` | a reference-list entry, parsed into `<ref>` |
| `Article:A:Article:FigureCaption` | figure caption |
| `Article:A:Article:TextListBullet / TextListNumbered` | `<p>` (list structure is not currently rebuilt) |
| `Article:A:Article:FIVE ASTERISKS` | `<p content-type="divider">` |
| `Book Review:B:BookReview:BookAuthor` | book-under-review details |
| `Book Review:B:BookReview:BookInfo` | book-under-review details |
| `Book Review:B:BookReview:ReviewAuthor` | the reviewer — becomes the piece's byline |
| `Book Review:B:BookReview:ReviewAuthorLocation` | the reviewer's affiliation |
| `Book Review:B:BookReviewTextFirstPara`, `…:Text` | `<p>` |
| `Book Review:B:BookReview:WorksCited` | reference entry |
| `Review Essay:RE:ReviewEssay:*` | the review-essay equivalents of the above |
| `Bibliography:BIB:Bibliography` | an entry in the Bibliography of British Columbia |
| `Bibliography:BIB:SubHeadOne` | heading inside the bibliography |
| `Tables:TABLE:TableName / TableNumber` | table caption |
| `Table of Contents:TOC:*` | read for section names and page numbers; never rendered |

Word styles that survive placement (`Normal`, `Body Text`, `Heading 1`,
`Quote`, `Caption`, `List Paragraph`…) are mapped to the least-wrong thing
rather than dropped, because they carry text.

---

## What is not a style

Three things the encoding depends on that are *not* paragraph styles:

**Character formatting is semantic.** Italic and bold runs are preserved, and
italics inside a reference entry are how the parser finds the container title.
Character styles are resolved by their definition (following `BasedOn`), not by
name, so a house style called `citation book` or `Unnamed Style 7` is read
correctly instead of guessed at.

**Footnotes are structural.** An IDML `<Footnote>` sits inside the sentence it
belongs to, so note numbering is derived rather than transcribed. A footnote
paragraph that turns up loose in the running text is a sign something came
unanchored, and the tool says so.

**Tracked changes are decisions.** An IDML file straight out of production can
still carry them. The parser accepts them — insertions kept, deletions dropped
— because re-opening an edit the editors already made would be a change to the
text, not a faithful reading of it.

---

## Pre-flight

Uploading an issue runs `bcs_idml.preflight()` first. It lists every paragraph
style the file uses and flags any the tool does not recognise, with a sample of
the text in it, **before** anything is imported — while the person who applied
the styles is still holding the file.

At the time of writing, issues 227, 228 and 229 use 28–30 distinct paragraph
styles between them and **all of them are in the vocabulary**.

When a new one appears, add it to `STYLE_MAP` in `bcs_styles.py` alongside the
old names rather than replacing them: old issues still need to parse.

---

## Vocabulary drift

Expected. The three issues tested already differ in which Word leftovers
they carry (`p1`, `Block Text`, `Normal first line indent`, `Article:Paragraph
Style 1`), and special issues introduce whole sections — 227 has an
*Introduction* and a *Research note*, 228 has a *Case Comment* — that no
paragraph style announces. Section names come from the issue's own table of
contents for exactly this reason, and unknown sections land in
`SECTION_DEFAULT` in `bcs_config.py`, which is a one-line fix rather than a
parser change.
