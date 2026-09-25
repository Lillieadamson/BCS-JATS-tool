# The project format (`projects/*.json`)

`format_version: 1`

One file per article. This is the tool's intermediate representation: what the
IDML parser produces, what the browser editor reads and writes, and what the renderer
turns into JATS. It sits deliberately between InDesign and XML and is committed to
neither.

**Why it's specified here.** Every other stage of the pipeline is defined by a
public standard — OOXML on one side, JATS on the other. This format is defined
only by the code that reads it. That's fine while the code is present and
someone understands it, and a problem otherwise. If you change the shape of this
file, **bump `PROJECT_FORMAT_VERSION` in `bcs_profiles.py`** and update this
document.

---

## Top level

```jsonc
{
  "id": "p11955bbd14",          // stable project id; also the filename
  "format_version": 1,          // bump on incompatible change
  "created": 1786...,           // unix timestamp
  "modified": 1786...,
  "source_filename": "BCS 229.idml",       // name only — the IDML is NOT kept
  "meta": { ... },              // see below
  "blocks": [ ... ],            // the body, in order
  "notes": [ ... ],             // endnotes, in order
  "ref_groups": [ ... ],        // Works Cited / Bibliography
  "bibliography": false,        // true if ref_groups sit under a Bibliography subhead
  "warnings": [ ... ]           // parser complaints, shown in the editor
}
```

## `meta` — 18 keys, all always present

| Key | Type | Notes |
|---|---|---|
| `title` | string | inline HTML: text plus `<i>` for a book title or court case named in it (becomes `<italic>` in `<article-title>`). Drafts from before September 2026 hold plain text, which reads the same way |
| `authors` | string | byline as printed; split downstream by `bcs_names.split_byline` |
| `section` | string | *Articles*, *Book Reviews*, *Soundworks*… read from the issue's table of contents; maps to `article-type` via `SECTION_MAP` |
| `seq` | number | position in the issue |
| `issue_number` | string | e.g. `"229"` |
| `year` | string | |
| `doi` | string | typed by hand, e.g. `10.14288/bcs.no226.196312` (issue number + OJS submission id). Printed in the galley's journal line and "How to Cite" box when filled in |
| `orcids` | string | one ORCID per author, byline order, joined with ` and ` (`-` for an author without one); becomes `<contrib-id contrib-id-type="orcid">` and the iD link beside the name |
| `fpage`, `lpage` | string | page range |
| `epub_date` | string | `YYYY-MM-DD`; becomes the OJS "published on" date |
| `keywords` | list of string | |
| `abstract_html` | string | inline HTML (see below). BC Studies does not print abstracts, so this is normally empty and typed in |
| `bios_html` | string | contributor bios as one field; kept in step with `bios` for older code paths |
| `bios` | list | one `{"name", "html"}` box per contributor. Filled at import from the issue's *Contributors* section, matched by whole name, then surname plus first name, then surname; when present it is what the renderer uses |
| `ack_html` | string | acknowledgements → `<ack>` |
| `funding_html` | string | funding statement → `<funding-group><funding-statement>` in article-meta (one per paragraph); the galley shows it after the acknowledgements |
| `ethics_html` | string | ethics statement → `<notes notes-type="ethics-statement">` in back |

At import, a run of *Acknowledgements*, *Funding* and *Ethics Statement* sub-heads that closes an article is moved out of the body into `ack_html`, `funding_html` and `ethics_html`. A run that does not close the article (other body sections follow) is left in the body.
| `book_info_html` | string | books under review |
| `reviewer_affiliation` | string | from the `ReviewAuthorLocation` paragraph |
| `subtitle` | string | inline HTML like `title`; kept separately as well as joined into `title`; the renderer peels it off the end of `title` and writes `<subtitle>` |
| `season` | string | *Spring*, *Autumn*… from the running head; becomes `<season>` in the collection `<pub-date>` |
| `short_title` | string | running head; `<alt-title alt-title-type="running-head">`. Blank at import |
| `issue_title` | string | a special issue's theme title, read from the top of the table of contents; `<issue-title>` |
| `guest_editors`, `issue_editors` | string | names joined with ` and `; each becomes its own `<contrib-group content-type="guest-editor"/"editor">`. Guest editors are read from the TOC's "Guest edited by" line |
| `pdf_url` | string | the PDF galley's address on OJS; becomes `<self-uri content-type="pdf">` and the galley's **PDF** button. Blank leaves the button out. Typed by hand once the article is up |
| `article_url` | string | the article's landing page on OJS; becomes `<self-uri content-type="ojs">`. Used by the **Share** button when there is no DOI — the DOI is preferred when there is one |
| `rights` | string | `"cc"` (Creative Commons) or `"copyright"` (the journal's copyright agreement). Blank takes `bcs_config.RIGHTS_DEFAULT`. Decides which `<license>` goes into `<permissions>` and what the galley's **Rights and permissions** button says. An article has one or the other, never both |

## `blocks` — the body

An ordered list. Each block is:

```jsonc
{ "kind": "p", "level": 1, "html": "The pedagogical context for these notes…" }
```

`kind` is one of **twelve** values — this is the tool's real content vocabulary:

| kind | Renders as |
|---|---|
| `p` | `<p>` |
| `heading` | opens a nested `<sec>` with `<title>`; `level` is the depth |
| `blockquote` | `<disp-quote>` |
| `verse` | `<verse-line>` inside a `<verse-group>` |
| `verse-break` | stanza break — ends the current `<verse-group>` |
| `epigraph` | `<disp-quote content-type="epigraph">` |
| `epigraph-source` | `<p content-type="epigraph-source">` |
| `divider` | `<p content-type="divider">` |
| `fig-caption` | figure caption with no image |
| `figure` | a figure: caption plus the linked graphic's filename |
| `audio` | an audio clip: `<media mimetype="audio">` with label, caption and the audio file's name. It stays where the block sits in the XML, but the galley prints the player at the **top of the article**, under the journal line and above the abstract |
| `table` | a `<table-wrap>`: label, caption, rows of cells, source note |

An `audio` block is shaped like a figure. `file` is a bare filename, never a
URL; `html` is the caption (a description, or a link to the transcript):

```jsonc
{ "kind": "audio", "id": "aud-1", "file": "hot-topic-episode-1.mp3",
  "label": "Episode 1", "caption_title": "Living Through the Heat Dome",
  "html": "Community members describe the summer of 2021." }
```

A file uploaded in the editor is kept in `projects/media/<project id>/` under
that name, goes into the download zip beside the galley `.html`, and is
uploaded to OJS as a dependent file of the HTML galley with exactly that Name.
A block with no `file` is left out of the XML (JATS requires the href) and
the renderer warns.

A `table` block keeps its caption in `html`, the way a figure does, and its
grid in `rows`. Every string is editor inline HTML, like any other block:

```jsonc
{ "kind": "table", "id": "tbl-1", "label": "Table 1",
  "html": "Ranks and tenures of RCMP detachment commanders",   // caption
  "header_rows": 0,                  // the first n rows become <thead>
  "rows": [ [ { "html": "<span class=\"sc\">White Rock detachment</span>",
                "th": true, "colspan": 2, "rowspan": 1 } ],
            [ { "html": "Constable William Fraser", "th": false, "colspan": 1, "rowspan": 1 },
              { "html": "1957–58", "th": false, "colspan": 1, "rowspan": 1 } ] ],
  "foot_html": "<p><i>Source</i>: …</p>" }  // <table-wrap-foot>
```

A cell covered by a merge is simply absent from its row, as in HTML.
Drafts saved before September 2026 held the finished JATS `<table>` string in
`html` and the caption in `caption`. The renderer still passes those through
unchanged, and the editor converts them to `rows` when the draft is opened
(`upgrade_tables()` in `bcs_editor.py`), so no version bump was needed.

## `notes` — endnotes

Ordered; note 1 is the first callout in the text.

```jsonc
{ "parts": [ { "kind": "p", "html": "Belcourt's critique…" },
             { "kind": "q", "html": "a block quote inside the note" } ] }
```

`kind` is `p` or `q` (block quote). A part may also carry `no_doi`, a list
of DOIs Crossref suggested for a citation in it that were turned down in the
Notes tab, so they are not offered again.

## `ref_groups` — the reference list

```jsonc
{ "title": "References",
  "refs": [ { "id": "cit001",
              "html": "Harris, Douglas C. 2008. <i>Landing Native Fisheries</i>. UBC Press." } ] }
```

Each ref stores its **display text**, not parsed fields. Parsing into
author/title/source/year/pages/DOI happens at render time in `analyze_ref()`,
which handles Chicago author-date (BC Studies' house style) as well as the
MLA shapes it was originally written for.
That's a deliberate choice — the editor corrects the entry as it should *print*,
and the parse is re-derived from the corrected text every time.

The `id` is what in-text citations point at.

---

## The inline HTML micro-format

Every `*_html` field and every block's `html` uses a deliberately tiny subset:

| Markup | Meaning |
|---|---|
| `<i>` | italic |
| `<b>` | bold |
| `<cite data-rid="cit010" data-status="auto" data-basis="context">21</cite>` | an in-text citation |
| `<sup data-fn="3">3</sup>` | a note callout |
| plain URLs | linkified at render time into `<ext-link>` |

**`data-status` on `<cite>` is the interesting one.** It records how confident
the tool is that this citation points at the right reference:

| value | meaning | editor shows |
|---|---|---|
| `auto` | matched, e.g. surname resolves to exactly one entry | yellow — the tool's guess |
| `ok` | a human confirmed it | green |
| `none` | not linked; stays plain text in the output | red |

`data-basis="context"` means it was a bare page number resolved against the most
recently named author in the running text — the guessiest case, flagged "check!"
in the Citations tab.

> **Note for anyone thinking about provenance:** this three-state certainty is
> the most interesting information in the file, and it is **thrown away at
> render time**. All three become an identical `<xref ref-type="bibr">`. TEI
> would express this with `@cert` and `@resp`; JATS has no clean equivalent,
> though `<custom-meta>` or `@specific-use` could carry it. Whether it *should*
> be preserved is an open question — see HANDOVER.md.

---

## Lifecycle, and what is actually archival

Drafts in `projects/` are **scratch**. In current practice they are deleted in
bulk once the XML has been generated and posted to OJS.

That makes `archive/*.archival.xml` the artifact that survives — which is why
the archival profile exists, and why every generated file carries its own
provenance in `<custom-meta-group>`.

If the workflow ever changes to retain projects, this JSON would be the better
master copy: it is more faithful than either XML rendering, it holds the
citation-confidence states that the XML drops, and it is not bent around any
viewer. In that case the thing to add is a documented backup of `projects/` and
a JSON Schema for this format.
