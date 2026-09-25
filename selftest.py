#!/usr/bin/env python3
"""
selftest.py -- render every saved project in every profile and check it.

Exit code is 0 if there are no errors, 1 otherwise, so you can wire it into
a git pre-commit hook later if you want.
"""

import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lxml import etree                                    # noqa: E402
from bcs_jats_render import (render_project, validate_xml, find_dtd,  # noqa: E402
                             check_odd_caps)
from bcs_profiles import PROFILES, TOOL_VERSION        # noqa: E402
from bcs_editor import title_plain                    # noqa: E402

SVRL = "{http://purl.oclc.org/dsdl/svrl}"
PARSER = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)


def load_schematron():
    path = HERE / "bcs-house-rules.sch"
    if not path.exists():
        return None, "bcs-house-rules.sch not found -- house rules skipped."
    try:
        from lxml.isoschematron import Schematron  # type: ignore
        return Schematron(etree.parse(str(path)), store_report=True), None
    except Exception as e:                                # pragma: no cover
        return None, f"Could not compile the Schematron: {e}"


def check_one(project, profile, schematron):
    """Returns (structural_errors, content_findings, warnings).

    Structural errors mean THE CODE IS BROKEN and fail the run.
    Content findings mean a particular draft is incomplete (no DOI yet, no
    page range yet) -- reported, but they don't fail the run, because a test
    that always fails is a test nobody runs."""
    errors, content, warnings = [], [], []

    try:
        xml, _w, _s, _r = render_project(project, profile)
    except Exception as e:
        return [f"render failed: {e!r}"], [], []

    # A stray capital inside a word in a title or heading. InDesign's AllCaps
    # draws a heading in capitals without changing the characters underneath,
    # so "ReLationship" looks right on the printed page and is still wrong in
    # the file -- and the galley's Outline repeats it. Proofreading the
    # journal cannot catch this; womp.
    check_odd_caps(project, warnings)

    try:
        doc = etree.fromstring(xml.encode("utf-8"), PARSER)
    except Exception as e:
        return [f"not well-formed: {e}"], [], []

    status, messages = validate_xml(xml)
    if status == "invalid":
        errors += [f"DTD: {m}" for m in messages[:5]]
    elif status == "skipped":
        warnings.append(f"DTD validation skipped ({messages[0] if messages else ''})")

    for ec in doc.iter("element-citation"):
        if len(ec) == 0 and not (ec.text or "").strip():
            errors.append("empty <element-citation> (DTD-invalid)")
            break

    ids = {e.get("id") for e in doc.iter() if e.get("id")}
    bad = sorted({x.get("rid") for x in doc.iter("xref")
                  if x.get("rid") and x.get("rid") not in ids})
    if bad:
        errors.append("xref points at missing id(s): " + ", ".join(bad[:5]))

    if schematron is not None:
        schematron.validate(doc)
        for el in schematron.validation_report.iter(SVRL + "failed-assert",
                                                    SVRL + "successful-report"):
            role = el.get("role") or "error"
            if role == "info":
                continue
            text = " ".join("".join(el.itertext()).split())
            (content if role == "error" else warnings).append(f"house rule: {text}")

    return errors, content, warnings


def main():
    print(f"bcs-jats-tool {TOOL_VERSION} self-test")
    dtd = find_dtd()
    print(f"JATS DTD: {dtd if dtd else 'NOT FOUND -- DTD validation will be skipped'}")

    schematron, sch_note = load_schematron()
    print(f"House rules: {'loaded' if schematron else sch_note}")

    files = sorted(glob.glob(str(HERE / "projects" / "p*.json")))
    print(f"Projects: {len(files)}\n")
    if not files:
        print("Nothing to check.")
        return 0

    total_err = 0
    total_content = 0
    summary = {}
    for f in files:
        try:
            project = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  {Path(f).name}: unreadable ({e})")
            total_err += 1
            continue
        label = (title_plain(project.get("meta", {}).get("title")) or Path(f).stem)[:48]
        for pname, profile in PROFILES.items():
            errors, content, warnings = check_one(project, profile, schematron)
            total_err += len(errors)
            total_content += len(content)
            for e in errors:
                summary.setdefault(("BROKEN", pname, e[:68]), []).append(label)
            for c in content:
                summary.setdefault(("content", pname, c[:68]), []).append(label)
            for w in warnings:
                summary.setdefault(("warn", pname, w[:68]), []).append(label)

    order = {"BROKEN": 0, "content": 1, "warn": 2}
    for (level, pname, msg), where in sorted(
            summary.items(), key=lambda kv: (order[kv[0][0]], -len(kv[1]), kv[0][1])):
        print(f"{level:8} [{pname:8}] x{len(where):<4} {msg}")
        if len(where) <= 3:
            for w in where:
                print(f"                            - {w}")

    n = len(files) * len(PROFILES)
    print()
    if total_err:
        print(f"FAILED: {total_err} structural error(s) across {n} renders. "
              "Something in the code is broken.")
    else:
        print(f"OK: {n} renders, no structural errors.")
    if total_content:
        print(f"     {total_content} content finding(s) -- drafts missing DOIs, "
              "page ranges etc. Not a code problem.")
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
