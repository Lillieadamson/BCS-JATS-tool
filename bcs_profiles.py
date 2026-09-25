#!/usr/bin/env python3
"""
bcs_profiles.py -- output profiles for the JATS renderer.

BC Studies publishes the HTML galley and the archival XML. The "lens" XML is
no longer uploaded to OJS; it is kept because the HTML galley is built from
it (the path every draft was tested on). Do not delete it without first
rendering every draft's HTML from the archival profile and comparing.

WHEN LENS IS FIXED OR OJS CHANGES VIEWERS
-----------------------------------------
Set ACCOMMODATIONS on the lens profile to an empty set, or just switch the
default profile to "archival". Nothing else needs to change
"""

from dataclasses import dataclass, field

# Bump this when the rendering logic changes in a way that would produce
# different XML from the same project
TOOL_VERSION = "1.0.0"

# Bump this when the shape of a projects/*.json file changes incompatibly.
# Every saved project records it; see bcs_editor.save_project.
PROJECT_FORMAT_VERSION = 1


@dataclass(frozen=True)
class Profile:
    """A named set of rendering decisions."""

    name: str
    description: str

    # --- reference rendering ------------------------------------------------
    # Emit <person-group><anonymous/></person-group> for references that have
    # no author at all. Lens skips any <ref> without a <person-group>, so
    # without this, films/websites/anonymous works vanish from the References
    # panel entirely. Untrue but necessary for display.
    anonymous_placeholder: bool = False

    # Put a whole work's own title (a book, a film, a standalone website) in
    # <article-title> rather than <source>. Lens reads ONLY <article-title>
    # for a citation's heading, falling back to <comment> then <source>, so
    # without this a book reference is headed by whatever landed in <comment>.
    # Semantically wrong: a book's title is a <source>, not an <article-title>.
    whole_work_title_as_article_title: bool = False

    # Wrap the citation title text in an <ext-link> so the reference is
    # clickable. Lens drops <ext-link> siblings, and the title is the only
    # field it renders as annotated text. Harmless to aggregators but not
    # something you would do if the viewer behaved.
    hyperlink_citation_title: bool = False

    # When there is no linkable title, append the URL to <comment> so Lens has
    # somewhere to show it ("Available from ..." pattern).
    url_into_comment: bool = False

    # --- notes --------------------------------------------------------------
    # Endnotes as a visible <sec sec-type="endnotes"> at the end of <body>
    # rather than a <fn-group> in <back>. The OJS Lens plugin's extractNotes
    # hook is an empty stub, so a back-matter fn-group is never displayed.
    # The body placement also happens to match the printed journal, so this
    # one is defensible on its own terms -- but it is driven by the viewer.
    notes_in_body: bool = False

    # --- bookkeeping --------------------------------------------------------
    # list of what this profile does to the XML written int the file itself.
    accommodations: tuple = field(default_factory=tuple)


LENS = Profile(
    name="lens",
    description=(
        "Galley XML for OJS. Accommodates verified defects in the eLife/Lens "
        "viewer. No longer uploaded by BC Studies; the HTML galley is built "
        "from it."
    ),
    anonymous_placeholder=True,
    whole_work_title_as_article_title=True,
    hyperlink_citation_title=True,
    url_into_comment=True,
    notes_in_body=True,
    accommodations=(
        "Author-less references carry <person-group><anonymous/></person-group> "
        "because the eLife/Lens viewer drops any <ref> without a "
        "person-group. The works are not necessarily anonymous.",
        "A whole work's own title (book, film, website) is placed in "
        "<article-title> as well as being the citation heading, because Lens "
        "reads only <article-title> for that heading. In correct JATS it "
        "would be <source>.",
        "Citation titles are wrapped in <ext-link> to make references "
        "clickable, because Lens ignores <ext-link> siblings.",
        "Where there is no linkable title, the URL is appended to <comment>.",
        "Endnotes are a <sec sec-type=\"endnotes\"> at the end of <body> "
        "rather than a <fn-group> in <back>, because the OJS Lens plugin "
        "never renders a back-matter fn-group. This also matches the printed "
        "journal.",
    ),
)


ARCHIVAL = Profile(
    name="archival",
    description=(
        "Clean JATS 1.4 with no viewer workarounds. Semantically correct: a "
        "book's title is a <source>, author-less works have no person-group, "
        "endnotes are a <fn-group> in <back>. Preservation copy."
    ),
    accommodations=(),
)


PROFILES = {p.name: p for p in (LENS, ARCHIVAL)}

# What /generate produces and what the editor offers for download.
DEFAULT_PROFILE = LENS


def get_profile(name):
    """Look up a profile by name; falls back to the default."""
    if isinstance(name, Profile):
        return name
    return PROFILES.get((name or "").strip().lower(), DEFAULT_PROFILE)
