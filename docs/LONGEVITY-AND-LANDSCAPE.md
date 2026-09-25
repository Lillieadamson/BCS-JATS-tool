> **Note.** This document was written for the Canadian Literature version of
> this tool and has been updated for BC Studies.

# Part 1 — Will the tool keep working?

## The dependency surface is very small #that's the main reason to be optimistic

Two direct dependencies: **Flask** and **lxml**. (python-docx is
gone: IDML is a zip of XML and is read with the standard library alone.)
Everything else in `requirements.txt` is something those three pull in.

All three are mature, widely used, and actively maintained. None is a startup's
side project. lxml in particular is a thin wrapper over libxml2, which has been
maintained since 1999 and is installed on essentially every Linux system on
earth. There is no framework here that goes out of fashion, no build step, no
JavaScript toolchain, no database, no cloud service, no API key, no vendor.

For comparison: the reason most small-journal publishing tools die is that they
depended on something that stopped existing. This one mostly does not.

## What will actually require maintenance, in likelihood order

**1. The InDesign style vocabulary**
Every time the journal's template changes or a new section type appears, a new
`CL ...` style shows up and the parser doesn't recognize it. Symptom: content
 missing. Fix: add the name to the right constant at the top of
`bcs_styles.py` and update `docs/BCS-STYLE-VOCABULARY.md`. The pre-flight check
names the offending style on upload, so you find out before importing. This is a
five-minute job **for someone who knows to look there** — which is why
that document exists.

**2. Python itself — every few years.**
The venv currently runs Python 3.13. The code needs 3.10+. When someone upgrades
macOS or Python and the venv breaks, the fix is to delete `venv/` and rebuild it
from `requirements.txt`. That is now a documented two-line operation rather than
a mystery. This is the single most likely reason the tool "stops working" for a
non-technical successor

**3. Lens / the OJS galley viewer — when OJS is upgraded.**
If the viewer changes, you edit flags in
`bcs_profiles.py` and re-render. **Nothing has to be re-encoded**, because the
project data was never what got bent. Worth being concrete about how fragile the
current viewer is: the OJS Texture plugin (the "official" JATS editing route)
has had no substantive release since OJS 3.1 and users report fatal errors on
3.3 and 3.4. The Lens galley plugin is a community fork of a 2014 eLife project.
Both are the kind of thing that stops working after an upgrade rather than being
formally retired.

**4. JATS versions — roughly never, and safely ignorable.**
You're on JATS 1.4 (2024) JATS is
deliberately and aggressively backward-compatible; 1.2 files that we used until like two days ago will be readable and
accepted indefinitely. 

## Risk:

The tool will keep running. The question is whether you know
**what to do when it misbehaves**. There is a difference between:

- *"The tool is broken"* → someone must read 4,200 lines of Python
- *"An article came out short, so an InDesign style is probably unrecognized —
  check `docs/CL-STYLE-VOCABULARY.md` and the constants at the top of
  `bcs_styles.py`"* → a competent non-author can do this.

The documentation, the Schematron and `selftest.py` exist to convert every
failure mode of the first kind into one of the second. 

**What would extend the tool's life most from here in order:**

1. Put it on GitHub with `requirements.txt` and the docs. (I have a private
   repo  with the docs and `requirements.txt`)
3. Record a screen capture of a full issue going through. Successors watch
   videos; they don't read docs.

---


## The commercial version of this tool is called eXtyles

[Inera's eXtyles](https://inera.com/key-product-features/) is the industry
standard for Word-to-JATS in scholarly publishing. It is a Word add-in that:

- uses **paragraph styles to create semantic structure** — Inera has a blog post
  literally titled ["How eXtyles Uses Paragraph Styles"](https://inera.com/blog/creating-semantic-structure-using-paragraph-styles-part-2-how-extyles-uses-paragraph-styles/);
- does **sophisticated bibliographic reference parsing** — this is what Inera is
  best known for;
- does **citation matching and linking**;
- exports **JATS**.

That is basically this tool feature for feature minus the journal-specific vocabulary.
It's used by large society publishers and priced accordingly. $$$$$$.


## More things

The University of Edinburgh ran a funded
[XML-based publishing in OJS project (2019)](https://www.ed.ac.uk/files/atoms/files/xml_publishing_in_ojs_-_project_summary_user_guide_0.pdf)
evaluating exactly these tools for library-published journals. Their finding:
all conversions require some degree of manual cleaning, so what's needed are tools that let journal editors make corrections without specialist software or
XML knowledge
 There's also a PKP/Library Publishing Forum survey,
["XML Publishing Workflows: Tools, Practices and the Future" (2020)](https://librarypublishing.org/wp-content/uploads/2020/05/PKP-XML-Publishing-Workflows.pdf),
and a paper with the wonderfully honest title
["How we tried to JATS XML"](https://www.researchgate.net/publication/341934227_How_we_tried_to_JATS_XML).

