# bcs_config.py 
#
# Everything that would have to change if this tool were pointed at a different
# journal lives here or in bcs_styles.py

JOURNAL = {
    "journal_id": "BCSTUDIES",
    "journal_title": "BC Studies: The British Columbian Quarterly",
    "abbrev_title": "BC Studies",
    # Print and electronic ISSNs. Leave a value as "" to omit that <issn> tag.
    "issn_ppub": "0005-2949",
    "issn_epub": "2819-5582",
    "publisher_name": "University of British Columbia",
    "publisher_loc": "Vancouver, Canada",
    # Used to build <article-id pub-id-type="publisher-id">.
    "id_prefix": "bcs",
}

# Who the copyright line names. Leave "" and the renderer credits the
# article's author(s). Name here is BC Studies and will show up on every article
COPYRIGHT_HOLDER = "BC Studies"

# The licence a CC-licensed article is published under. It goes into the XML
# as <license license-type="open-access"> and sits behind the galley's
# "Rights and permissions" button.
#
# From 2027 BC Studies publishes under this licence. Everything already in the
# archive was published under the journal's copyright agreement instead, so an
# article carries one or the other, never both -- see RIGHTS_DEFAULT below and
# the per-article "rights" field in the editor's Metadata tab.
#
# Set "url" to "" to leave the licence out entirely.
LICENSE = {
    "url": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
    "name": "Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International License",
    "text": ("This work is licensed under a Creative Commons "
             "Attribution-NonCommercial-NoDerivatives 4.0 International License."),
    # NOT what the galley shows: the XSLT picks the badge from "url" above
    # (template cc-badge-img in xslt/jats-to-html.xsl). Changing this line
    # changes nothing on the page; kept for reference.
    "badge": "https://i.creativecommons.org/l/by-nc-nd/4.0/88x31.png",
}

# The other half of the pair: articles published under the journal's own
# copyright agreement rather than a Creative Commons licence. Every
# article up to 2026.
#
# Every one of these articles gets a "Rights and permissions" button showing
# "text". "url" is deliberately empty because the journal has no page to link
# to yet; while it is empty the button shows the text alone, with no link.
# If you put an address here later, a "Read the copyright and permissions policy"
# link appears under the text on the next generate.
COPYRIGHT_AGREEMENT = {
    "url": "",
    "name": "BC Studies copyright agreement",
    "text": "For content published between 1969–2026, copyright rests with BC Studies. To make requests for permissions, please contact info@bcstudies.ubc.ca",
}

# The first year of publication that carries a Creative Commons licence.
#
# An article whose "rights" field is left blank gets the CC licence if it is
# dated this year or later, and the copyright agreement if it is older. 
#
# Set to 0 to switch the rule off, in which case every blank field takes
# RIGHTS_DEFAULT below.
CC_FROM_YEAR = 2027

# What a blank "rights" field falls back to when the article has no usable
# year, or when CC_FROM_YEAR is 0. "cc" uses LICENSE; "copyright" uses
# COPYRIGHT_AGREEMENT.
RIGHTS_DEFAULT = "copyright"

# Fonts the typesetter switches to for characters the body font lacks --
# Indigenous-language orthographies (ləkʷəŋən, hən̓q̓əmin̓əm̓), IPA, combining
# marks. A run set in one of these is marked
# <styled-content style-type="special-characters"> so the HTML galley can
# guarantee it a font that has the glyphs. Names are matched case-insensitively
# as substrings of InDesign's AppliedFont.
SPECIAL_CHAR_FONTS = (
    "First Nations Unicode", "Aboriginal Serif", "Aboriginal Sans",
    "Junicode", "BabelStone", "Gentium", "Charis SIL", "Doulos SIL",
    "Noto Sans Canadian Aboriginal", "Euphemia",
)

# DOIs -- UNUSED. Nothing imports these. BC Studies DOIs are per article and
# their suffix is the OJS submission ID, so they cannot be minted here: copy
# each one from OJS into the DOI field of the editor's Metadata tab.
DOI_PREFIX = ""            # e.g. "10.14288"
DOI_PATTERN = ""           # e.g. "{prefix}/bcs.no{issue}.{seq}"

# Crossref DOI lookup (References tab). Crossref does not verify the address;
# it only uses it to put the request on the "polite" pool, which is faster
# (0.4s between calls instead of 1.1s) and far less likely to be rate-limited.
# Leave "" to use the anonymous pool. Any real address works 
CROSSREF_MAILTO = "bcstudies@ubc.ca"       # e.g. "bcstudies@ubc.ca"

# The journal's citation style runs Chicago in both flavours:
# author-date with a reference list in the social-science articles, and
# notes-bibliography with footnotes carrying full citations in the historical
# ones. The reference parser handles both.
#
# UNUSED: nothing reads this constant; changing it has no effect.
CITATION_STYLE = "chicago"

# Section name (lowercased) -> JATS article-type and the <subj-group> text.
#
# The keys are the section names BC Studies prints, a new section in a special issue
# lands in SECTION_DEFAULT and is easy to add here.
SECTION_MAP = {
    "articles":            {"article-type": "research-article",  "subject": "ARTICLE"},
    "article":             {"article-type": "research-article",  "subject": "ARTICLE"},
    "introduction":        {"article-type": "introduction",      "subject": "INTRODUCTION"},
    "editorial":           {"article-type": "editorial",         "subject": "EDITORIAL"},
    "the front":           {"article-type": "other",             "subject": "THE FRONT"},
    "this space here":     {"article-type": "article-commentary", "subject": "THIS SPACE HERE"},
    "research note":       {"article-type": "research-article",  "subject": "RESEARCH NOTE"},
    "research notes":      {"article-type": "research-article",  "subject": "RESEARCH NOTE"},
    "case comment":        {"article-type": "article-commentary", "subject": "CASE COMMENT"},
    "soundwork":           {"article-type": "other",             "subject": "SOUNDWORK"},
    "soundworks":          {"article-type": "other",             "subject": "SOUNDWORK"},
    "podcast":             {"article-type": "other",             "subject": "PODCASTS & NEW MEDIA"},
    "podcasts":            {"article-type": "other",             "subject": "PODCASTS & NEW MEDIA"},
    "podcasts & new media": {"article-type": "other",            "subject": "PODCASTS & NEW MEDIA"},
    "book reviews":        {"article-type": "book-review",       "subject": "BOOK REVIEW"},
    "review essays":       {"article-type": "book-review",       "subject": "REVIEW ESSAY"},
    "exhibition, film, and new media reviews":
                           {"article-type": "book-review",       "subject": "EXHIBITION, FILM, AND NEW MEDIA REVIEW"},
    "exhibition review":   {"article-type": "book-review",       "subject": "EXHIBITION REVIEW"},
    "film review":         {"article-type": "book-review",       "subject": "FILM REVIEW"},
    "bibliography of bc":  {"article-type": "other",             "subject": "BIBLIOGRAPHY OF BRITISH COLUMBIA"},
    "bibliography of british columbia":
                           {"article-type": "other",             "subject": "BIBLIOGRAPHY OF BRITISH COLUMBIA"},
    "contributors":        {"article-type": "other",             "subject": "CONTRIBUTORS"},
    "bc studies prize":    {"article-type": "other",             "subject": "BC STUDIES PRIZE"},
    "photo essay": {"article-type": "research-essay", "subject": "PHOTO ESSAY"},
}
SECTION_DEFAULT = {"article-type": "other", "subject": "ARTICLE"}
