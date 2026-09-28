#!/usr/bin/env python3

"""
app.py -- web front end. 

Run locally:
    pip install flask lxml
    python app.py
Then open http://localhost:5002
"""
# Web front end for the BC Studies JATS and HTML Editor.
# Created August-September 2026 by Lillie Adamson for BC Studies.
# Maintained by BC Studies -- see BCS-JATS-Tool-User-Guide.docx.
#
# WHAT BC STUDIES PUBLISHES: the HTML galley (plus style.css, logo.png and any
# images/audio as dependent files) goes on OJS. The archival XML is the
# preservation copy and is NOT uploaded to OJS. The "lens" profile still
# exists only because the HTML is built from it -- see bcs_profiles.py.
import io
import json
import zipfile
import threading
import time
import uuid
from pathlib import Path

from flask import (Flask, abort, jsonify, redirect, render_template_string,
                   request, send_from_directory, send_file)
from markupsafe import escape
from werkzeug.utils import secure_filename

from bcs_idml import parse_issue, preflight
from bcs_jats_render import transform_xml_with_xslt
from bcs_config import SECTION_MAP
from bcs_editor import (
    PROJECTS_DIR, delete_project, list_projects, load_project, media_dir,
    piece_to_project, refresh_citations, save_project, title_html, upgrade_tables,
)
import bcs_crossref
from bcs_jats_render import (
    find_dtd, issue_slug, project_basename, project_filename, render_project,
    validate_xml,
)
from bcs_profiles import ARCHIVAL, LENS, PROFILES, get_profile


# projects/ is scratch and can be cleared out, but the archival XML
# is the copy meant to outlive OJS. Basically so deleting a
# draft doesn't delete the preservation copy.
ARCHIVE_DIR = Path(__file__).resolve().parent / "archive"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024   # a podcast episode as WAV runs large

# uploads waiting for the "which pieces do you want?" step
IMPORTS = {}
IMPORTS_LOCK = threading.Lock()


# =============================================================================
# shared page 
# =============================================================================

BASE_CSS = """
  * { box-sizing: border-box; }
  body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif; margin: 0; color: #1f2937; background: #ffffff; font-size: 1.1rem; }
  .top { background: #0a0761; color: #ffffff; padding: 25px 40px; display: flex; align-items: center; gap: 16px; }
  .top h1 { font-size: 1.50rem; margin: 0; font-weight: 600;  }
  .wrap { max-width: 1000px; margin: 24px auto; padding: 0 20px 60px; }
  button, .btn { background: #0a0761; color: #ffffff; border: none; padding: 8px 18px; border-radius: 6px; font-size: .95rem; cursor: pointer; text-decoration: none; display: inline-block; }
  button:hover, .btn:hover { background: #234a73; }
  button.ghost { background: #0a0761; color: #ffffff; }
  button.small { padding: 3px 10px; font-size: .8rem; color: #FFFFFF; background-color: #0a0761; }
  .btn.small { padding: 3px 10px; font-size: .8rem; }
  .top a, .top a:visited { color: #ffffff; text-decoration: none; font-size: 1.3rem; }
  button.danger { background: #fef2f2; color: #b42318; }
  .error { color: #b42318; margin-top: 16px; }
  .hint { color: #475569; font-size: .88rem; }
  .card { background-color: #ffffff; border: 1px solid #dfe3e8; border-radius: 8px; padding: 16px 20px; margin: 12px 0; color: #1f2937; }
  input[type=text] { width: 100%; padding: 7px 9px; border: 1px solid #cbd5e1; border-radius: 5px; font-size: .95rem; }
  label { display: block; font-size: .78rem; color: #2c4a68; margin: 8px 0 2px; font-weight: 600; }
  .tag { display: inline-block; font-size: .72rem; background: #edf5ff; color: #2f5d8a; border-radius: 10px; padding: 1px 9px; margin-right: 6px; }
  table { border-collapse: collapse; width: 100%; }
  td, th { padding: 8px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; font-size: .95rem; }
  .hint1 { color: #475569; font-size: .88rem; }
  .logo { display: flex; justify-content: center; width: 100%; height: 100%;}
  .image { width: 100%; max-width: 500px; height: auto; object-fit: cover; display: block; justify-content: center; text-align: center; margin: 0 auto; }
  .card-front { background-color: #ffffff; border: 2px solid #0a0761; border-radius: 8px; padding: 16px 20px; margin: 12px 0; color: #1f2937; display: flex; flex-direction: column; align-items: center; text-align: center; }
  .listtools input[type=text] { flex: 1; max-width: 420px; }
  .pager { display: flex; gap: 5px; flex-wrap: wrap; align-items: center; margin-top: 12px; justify-content: center; }
  .pager button { padding: 5px 12px; font-size: .9rem; }
  .pager button.pgnow { background: #2f5d8a; color: #fff; }
  .draftrow a:link { color: #1B3185; text-decoration: none; }
  #draftcount { margin-left: 12px; font-size: .88rem; color: #475569; }
  #drafttable { margin-top: 12px; }
"""
def page(title, body_html):
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{title}</title><link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif:ital,wght@0,100..900;1,100..900&display=swap" rel="stylesheet">
<script src="https://kit.fontawesome.com/c82e8dae1a.js" crossorigin="anonymous"></script>
<style>{BASE_CSS}</style></head><body>
<div class="top"><h1>Markup Editor</h1>
<a href="/" aria-label="Home">
      <i class="fa-solid fa-house"></i></a>
</div>
<div class="wrap">{body_html}</div></body></html>"""


# =============================================================================
# HOME: project list + upload
# =============================================================================

DRAFTS_JS = r"""
// search + paginate the draft list
(function(){
  var PER = 15;
  var rows = [].slice.call(document.querySelectorAll('#drafttable tr.draftrow'));
  var box = document.getElementById('draftsearch');
  var pager = document.getElementById('draftpager');
  var count = document.getElementById('draftcount');
  if (!rows.length || !box) return;
  var page = 1;
  function draw(){
    var terms = box.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    var hits = rows.filter(function(r){
      return terms.every(function(t){ return (r.dataset.hay || '').indexOf(t) !== -1; });
    });
    var pages = Math.max(1, Math.ceil(hits.length / PER));
    if (page > pages) page = pages;
    var start = (page - 1) * PER;
    rows.forEach(function(r){ r.style.display = 'none'; });
    hits.slice(start, start + PER).forEach(function(r){ r.style.display = ''; });
    if (!hits.length) {
      count.textContent = 'No drafts match “' + box.value.trim() + '”.';
    } else {
      count.textContent = 'Showing ' + (start + 1) + '–' + Math.min(start + PER, hits.length)
        + ' of ' + hits.length + (terms.length ? ' matching' : '') + ' draft' + (hits.length === 1 ? '' : 's') + '.';
    }
    pager.innerHTML = '';
    if (pages > 1) {
      var mk = function(label, target, disabled, now){
        var b = document.createElement('button');
        b.className = 'small ghost' + (now ? ' pgnow' : '');
        b.textContent = label;
        if (disabled) { b.disabled = true; b.style.opacity = '.45'; b.style.cursor = 'default'; }
        else { b.onclick = function(){ page = target; draw(); box.scrollIntoView({block:'center', behavior:'smooth'}); }; }
        pager.appendChild(b);
      };
      mk('← prev', page - 1, page === 1, false);
      for (var i = 1; i <= pages; i++) mk(String(i), i, false, i === page);
      mk('next →', page + 1, page === pages, false);
    }
  }
  box.addEventListener('input', function(){ page = 1; draw(); });
  draw();
})();
"""


@app.route("/")
def index():
    error = request.args.get("error", "")
    rows = []
    issues = []
    for p in list_projects():
        when = time.strftime("%b %d, %Y %H:%M", time.localtime(p["modified"]))
        # everything the search box matches against flattened into one string
        hay = " ".join([p["title"], p["authors"], p["section"], str(p["issue"])]).lower()
        slug = issue_slug({"meta": {"issue_number": str(p["issue"])}})
        if slug != "UNKNOWN" and slug not in issues:
            issues.append(slug)
        rows.append(
            f"<tr class='draftrow' data-hay=\"{escape(hay)}\"><td><a href='/edit/{p['id']}'><b>{p['title_html'] or '(untitled)'}</b></a><br>"
            f"<span class='hint'>{escape(p['authors'])}</span></td>"
            f"<td>{escape(p['section'])}</td><td>{escape(p['issue'])}</td><td>{when}</td>"
            f"<td>{'&#10003; XML generated' if p['has_xml'] else ''}</td>"
            f"<td><form method='post' action='/delete/{p['id']}' style='display:inline' "
            f"onsubmit=\"return confirm('Delete this article draft?');\">"
            f"<button class='small danger'>delete</button></form></td></tr>")
    table = ("<table id='drafttable'><tr><th>Title</th><th>Section</th><th>Issue</th><th>Edited</th><th></th><th></th></tr>"
             + "".join(rows) + "</table>") if rows else "<p class='hint'>No article drafts yet &mdash; upload an issue to start.</p>"
    search_box = ("<div class='listtools'>"
                  "<input type='text' id='draftsearch' placeholder='Search drafts \u2014 title, author, section, or issue\u2026' autocomplete='off'>"
                  "<span class='hint' id='draftcount'></span></div>") if rows else ""
    pager = "<div class='pager' id='draftpager'></div>" if rows else ""
    issues.sort(key=lambda i: (0, -int(i)) if i.isdigit() else (1, 0))
    issue_dl = ("<p class='hint'>Download a WHOLE issue &mdash; every draft's HTML galley, "
                "its dependent files and the archival XML in one zip: "
                + " ".join(f"<a class='btn small' href='/download_issue/{escape(i)}'>{escape(i)}</a>"
                           for i in issues) + "</p>") if issues else ""
    dtd_note = "" if find_dtd() else ("<p class='hint'>&#9888; JATS 1.4 DTD folder not found next to the tool "
                                      "&mdash; XML will still generate, but validation will be skipped.</p>")
    body = f"""
    <div class="image">
      <img class="logo" src="/logo.png" alt="BC Studies Logo"/></div>
      <div class="card-front">
        <h2 style="margin-top:0">Upload an issue (.idml)</h2>
        <p class="hint1">Export the issue from InDesign as IDML
        (<i>File &rsaquo; Export &rsaquo; InDesign Markup</i>) and upload it here.
        The tool reads the BC Studies paragraph styles &mdash; <code>A:Article:TITLE</code>,
        <code>B:BookReview:BookInfo</code> and the rest &mdash; and splits the
        issue into one editable draft per piece.</p>
        <form method="post" action="/upload" enctype="multipart/form-data">
          <input type="file" name="idml" accept=".idml" required>
          <button type="submit">Upload &amp; check</button>
        </form>
        {f"<p class='error'>{escape(error)}</p>" if error else ""}
      </div>
      <h2>Article Library</h2>
      {issue_dl}
      {search_box}
      {table}
      {pager}
      {dtd_note}
      <script>{DRAFTS_JS}</script>
    """
    return page("BC Studies Markup Editor", body)


@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("idml")
    fname = (f.filename or "") if f else ""   # a hand-rolled POST can omit it
    if not f or not fname.lower().endswith(".idml"):
        return redirect("/?error=Please+choose+an+.idml+file+exported+from+InDesign.")
    data = f.read()
    try:
        check = preflight(io.BytesIO(data))
        pieces, issue_meta = parse_issue(io.BytesIO(data))
    except Exception as e:
        return redirect(f"/?error=Could+not+read+that+IDML:+{escape(str(e))}")
    if not pieces:
        return redirect("/?error=No+pieces+found+--+does+the+file+use+the+BC+Studies+paragraph+styles?")

    job_id = uuid.uuid4().hex[:12]
    with IMPORTS_LOCK:
        cutoff = time.time() - 6 * 3600
        for k in [k for k, v in IMPORTS.items() if v["created"] < cutoff]:
            del IMPORTS[k]
        IMPORTS[job_id] = {"pieces": pieces, "issue_meta": issue_meta,
                           "filename": Path(fname).name, "created": time.time()}

    # The pre-flight report comes first
    if check["unknown"]:
        rows = "".join(
            f"<tr><td><code>{escape(st)}</code></td><td>{n}</td>"
            f"<td class='hint'>{escape(sample)}</td></tr>"
            for st, n, sample in check["unknown"])
        preflight_html = f"""
          <div class="card" style="border-color:#f0c36d;background:#fffbf0">
            <h3 style="margin-top:0">{len(check['unknown'])} paragraph style(s) not in the BC Studies vocabulary</h3>
            <p class="hint">Text in these styles will still be imported, as plain
            paragraphs, but nothing will know what it is. Either fix the style in
            InDesign and export again, or add the style to <code>bcs_styles.py</code>.</p>
            <table><tr><th>Style</th><th>Paragraphs</th><th>First one reads</th></tr>{rows}</table>
          </div>"""
    else:
        preflight_html = (f"<p class='hint'>&#10003; All {len(check['known'])} paragraph "
                          f"styles in this file are in the BC Studies vocabulary.</p>")

    rows = []
    for i, piece in enumerate(pieces):
        title = " ".join(piece.title.split()) or "(untitled)"
        byline = " ".join(piece.byline.split())
        n_refs = sum(len(g.get("html", [])) for g in piece.ref_groups)
        pages = f"pp. {piece.fpage}&ndash;{piece.lpage}" if piece.fpage else ""
        tags = "".join(f"<span class='tag'>{escape(t)}</span>" for t in
                       [piece.section or "?"]
                       + ([pages] if pages else [])
                       + ([f"{n_refs} refs"] if n_refs else [])
                       + ([f"{len(piece.notes)} notes"] if piece.notes else [])
                       + ([f"{len(piece.figures)} figs"] if piece.figures else []))
        rows.append(f"<tr><td><input type='checkbox' name='include_{i}' checked></td>"
                    f"<td><b>{escape(title)}</b><br><span class='hint'>{escape(byline)}</span></td>"
                    f"<td>{tags}</td></tr>")
    issue_line = " ".join(x for x in (
        f"No. {issue_meta.get('issue_number', '')}" if issue_meta.get("issue_number") else "",
        issue_meta.get("season", ""), issue_meta.get("year", "")) if x)
    body = f"""
      <h2>Import from {escape(Path(fname).name)}</h2>
      <p class="hint">{escape(issue_line)} &mdash; {len(pieces)} pieces found.
      Each ticked piece becomes its own editable article draft.</p>
      {preflight_html}
      <form method="post" action="/import/{job_id}">
        <div class="card"><table><tr><th></th><th>Piece</th><th></th></tr>{"".join(rows)}</table></div>
        <button type="submit">Import selected pieces</button>
      </form>"""
    return page("Import pieces", body)


@app.route("/import/<job_id>", methods=["POST"])
def do_import(job_id):
    with IMPORTS_LOCK:
        job = IMPORTS.pop(job_id, None)
    if job is None:
        return redirect("/?error=That+upload+expired+--+please+upload+again.")
    created = []
    for i, piece in enumerate(job["pieces"]):
        if f"include_{i}" not in request.form:
            continue
        project = piece_to_project(piece, job["issue_meta"], seq=i + 1,
                                   source_filename=job["filename"])
        save_project(project)
        created.append(project["id"])
    if len(created) == 1:
        return redirect(f"/edit/{created[0]}")
    return redirect("/")


@app.route("/delete/<pid>", methods=["POST"])
def delete(pid):
    try:
        delete_project(pid)
    except (ValueError, OSError) as e:
        return redirect(f"/?error=Could+not+delete:+{escape(str(e))}")
    return redirect("/")


# =============================================================================
# JSON API used by the editor page
# =============================================================================

@app.route("/save/<pid>", methods=["POST"])
def save(pid):
    project = request.get_json(force=True)
    project["id"] = pid  
    save_project(project)
    return jsonify({"ok": True, "saved": time.time()})


# ---------- audio and image files for "Audio clip" and "Figure" blocks ----------
# Kept in projects/media/<pid>/ under the name the block (and so the XML and
# HTML) refers to. They go into the download zip beside the galley .html, and
# are uploaded to OJS as dependent files of the galley under that name.
AUDIO_EXTS = {"mp3", "m4a", "aac", "wav", "ogg", "oga", "opus", "flac", "webm"}
IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "tif", "tiff", "webp", "svg"}


def _looks_like_audio(data, ext):
    """True if the bytes really are the audio container the filename claims.
    A download that failed often arrives as an HTML error page saved under an
    .mp3 name, and the player then sits at 0:00 with nothing to say about it,
    so the name alone is not enough."""
    if ext == "wav":
        return data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if ext in ("ogg", "oga", "opus"):
        return data[:4] == b"OggS"
    if ext == "flac":
        return data[:4] == b"fLaC"
    if ext == "webm":
        return data[:4] == b"\x1aE\xdf\xa3"
    if ext == "m4a":
        return data[4:8] == b"ftyp"
    # mp3 and aac: an ID3 tag, or a bare stream whose first bytes are a
    # frame sync (11 set bits)
    return data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF
                                  and (data[1] & 0xE0) == 0xE0)


def _looks_like_image(data, ext):
    """Same check as _looks_like_audio, for figure images."""
    if ext in ("jpg", "jpeg"):
        return data[:3] == b"\xff\xd8\xff"
    if ext == "png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    if ext == "gif":
        return data[:6] in (b"GIF87a", b"GIF89a")
    if ext in ("tif", "tiff"):
        return data[:4] in (b"II*\x00", b"MM\x00*")
    if ext == "webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if ext == "svg":
        head = data[:1024].lstrip().lower()
        return head.startswith(b"<?xml") or head.startswith(b"<svg") or b"<svg" in head
    return False


@app.route("/media/<pid>", methods=["POST"])
def upload_media(pid):
    f = request.files.get("file")
    name = secure_filename(f.filename or "") if f else ""
    if not name:
        return jsonify({"ok": False, "error": "No file received."}), 400
    ext = name.rsplit(".", 1)[-1].lower()
    # the block that sent it says which kind it expects
    want = request.form.get("kind", "audio")
    if want == "image" and ext not in IMAGE_EXTS:
        return jsonify({"ok": False, "error":
                        f"{name} is not an image file this tool knows. Hmmm. Use a JPG "
                        "or PNG (or GIF, TIFF, WebP, SVG)."}), 400
    if want != "image" and ext not in AUDIO_EXTS:
        return jsonify({"ok": False, "error":
                        f"{name} is not an audio file this tool knows. Hmmm. Use an MP3 "
                        "(or M4A, WAV, OGG)."}), 400
    try:
        d = media_dir(pid)
    except ValueError:
        return jsonify({"ok": False, "error": "Bad draft id."}), 400
    data = f.read()
    if want == "image" and not _looks_like_image(data, ext):
        return jsonify({"ok": False, "error":
                        f"{name} is named like an image but its contents are not -- "
                        "a download that failed and saved the web page instead does "
                        "this. Open it in Preview to check then upload the real "
                        "file."}), 400
    if want != "image" and not _looks_like_audio(data, ext):
        return jsonify({"ok": False, "error":
                        f"{name} is named like audio but its contents are not -- a "
                        "download that failed and saved the web page instead does "
                        "this. Open it in a music player to check, then upload the "
                        "real file."}), 400
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(data)
    return jsonify({"ok": True, "file": name, "bytes": (d / name).stat().st_size})


@app.route("/media/<pid>/<name>")
def get_media(pid, name):
    try:
        d = media_dir(pid)
    except ValueError:
        abort(404)
    return send_from_directory(d, name, conditional=True)


@app.route("/media_list/<pid>")
def list_media(pid):
    try:
        d = media_dir(pid)
    except ValueError:
        abort(404)
    names = sorted(x.name for x in d.iterdir() if x.is_file()) if d.exists() else []
    return jsonify({"ok": True, "files": names})


def _media_entries(project):
    """(name-in-zip, bytes) for the audio and figure images this article's
    blocks name, in the HTML folder beside the .html so the galley plays and
    shows them straight off disk. A block naming a file that was never
    uploaded gets a note instead."""
    issue = issue_slug(project)
    out, seen = [], set()
    try:
        d = media_dir(project.get("id", ""))
    except ValueError:
        return out
    for b in project.get("blocks", []):
        kind = b.get("kind")
        name = (b.get("file") or "").strip() if kind in ("audio", "figure") else ""
        if not name or name in seen:
            continue
        seen.add(name)
        src = d / name
        if src.is_file():
            out.append((f"{issue}/HTML/{name}", src.read_bytes()))
        elif kind == "figure":
            out.append((f"{issue}/HTML/{name}-NOT-INCLUDED.txt",
                        (f"The article shows {name}, but it was never uploaded to "
                         f"the tool, so it is not in this zip. Put {name} beside "
                         f"the .html, and upload it to OJS as a dependent file "
                         f"of the HTML galley named exactly \"{name}\".\n").encode("utf-8")))
        else:
            out.append((f"{issue}/HTML/{name}-NOT-INCLUDED.txt",
                        (f"The article plays {name}, but it was never uploaded to "
                         f"the tool, so it is not in this zip. Put {name} beside "
                         f"the .html, and upload it to OJS as a dependent file of "
                         f"the HTML galley named exactly \"{name}\".\n").encode("utf-8")))
    return out


@app.route("/rescan/<pid>", methods=["POST"])
def rescan(pid):
    project = request.get_json(force=True)
    project["id"] = pid
    refresh_citations(project)
    save_project(project)
    return jsonify({"ok": True, "project": project})


@app.route("/crossref/<pid>", methods=["POST"])
def crossref(pid):
    """DOI suggestions for the reference ids the editor asks about."""
    data = request.get_json(force=True)
    try:
        results = bcs_crossref.lookup_groups(data.get("ref_groups") or [],
                                             data.get("ids") or [])
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
    return jsonify({"ok": True, "results": results})


@app.route("/crossref_notes/<pid>", methods=["POST"])
def crossref_notes(pid):
    """DOI suggestions for the full citations inside the note paragraphs asked about."""
    data = request.get_json(force=True)
    try:
        results = bcs_crossref.lookup_notes(data.get("notes") or [],
                                            data.get("parts") or [])
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
    return jsonify({"ok": True, "results": results})


@app.route("/generate/<pid>", methods=["POST"])
def generate(pid):
    project = request.get_json(force=True)
    project["id"] = pid
    save_project(project)

    # The "lens" copy is what the HTML galley is built from. It is saved to
    # projects/ (the home page's "XML generated" tick reads it) but is not
    # offered for upload: BC Studies does not put XML on OJS.
    try:
        xml, warnings, stats, ref_rows = render_project(project, LENS)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Conversion failed: {e}"}), 500
    status, messages = validate_xml(xml)
    fname = project_filename(project, LENS)
    (PROJECTS_DIR / f"{pid}.xml").write_text(xml, encoding="utf-8")

    # The preservation copy: clean JATS with no viewer workarounds.
    archive_note = ""
    archive_ok = False
    try:
        axml, _aw, _as, _ar = render_project(project, ARCHIVAL)
        (PROJECTS_DIR / f"{pid}.archival.xml").write_text(axml, encoding="utf-8")
        ARCHIVE_DIR.mkdir(exist_ok=True)
        aname = project_filename(project, ARCHIVAL)
        (ARCHIVE_DIR / aname).write_text(axml, encoding="utf-8")
        astatus, amessages = validate_xml(axml)
        archive_ok = True
        archive_note = f"archive/{aname}"
        if astatus == "invalid":
            warnings.append("The archival copy did not validate: "
                            + "; ".join(amessages[:3]))
    except Exception as e:
        warnings.append(f"Could not write the archival copy: {e}")

    return jsonify({"ok": True, "filename": fname, "xml": xml,
                    "validation": {"status": status, "messages": messages},
                    "warnings": warnings, "stats": stats,
                    "archive_ok": archive_ok, "archive_path": archive_note,
                    "archive_filename": project_filename(project, ARCHIVAL),
                    "issue_folder": issue_slug(project)})


@app.route("/download/<pid>")
def download(pid):
    return _download_profile(pid, "lens")


@app.route("/download/<pid>/<profile>")
def download_profile(pid, profile):
    return _download_profile(pid, profile)


def _download_profile(pid, profile_name):
    prof = get_profile(profile_name)
    suffix = "" if prof.name == "lens" else f".{prof.name}"
    xml_path = PROJECTS_DIR / f"{pid}{suffix}.xml"
    if not xml_path.exists():
        return redirect(f"/edit/{pid}")
    project = load_project(pid)
    return send_file(io.BytesIO(xml_path.read_bytes()), as_attachment=True,
                     mimetype="application/xml",
                     download_name=project_filename(project, prof))


@app.route("/download_html/<pid>")
def download_html(pid):
    return _download_profile_html(pid, "lens")


@app.route("/download_html/<pid>/<profile>")
def download_profile_html(pid, profile):
    return _download_profile_html(pid, profile)


def _download_profile_html(pid, profile_name):
    prof = get_profile(profile_name)
    project = load_project(pid)
    # render the XML for the requested profile
    xml, warnings, stats, ref_rows = render_project(project, prof)
    # default XSLT next to this file
    xslt_path = Path(__file__).resolve().parent / "xslt" / "jats-to-html.xsl"
    if not xslt_path.exists():
        return _error_page(pid, "The HTML could not be built: the file "
                                "xslt/jats-to-html.xsl is missing from the tool folder.")
    try:
        html_text = transform_xml_with_xslt(xml, xslt_path)
    except Exception as e:
        # Most likely cause: a recent edit to xslt/jats-to-html.xsl. The
        # message below names the line; undo that edit and try again.
        return _error_page(pid, f"The HTML could not be built: {e}")
    return send_file(io.BytesIO(html_text.encode('utf-8')), as_attachment=True,
                     mimetype="text/html", download_name=project_filename(project, prof).rsplit('.',1)[0] + '.html')


def _error_page(pid, message):
    """A plain page saying what went wrong, instead of bouncing
    back to the editor."""
    return page("Something went wrong", f"""
      <div class="card"><h2 style="margin-top:0">Something went wrong</h2>
      <p>{escape(message)}</p>
      <p class="hint">If you recently edited <code>xslt/jats-to-html.xsl</code> or
      <code>style.css</code>, undo that edit and try again. Otherwise send this
      message to whoever looks after the tool.</p>
      <p><a class="btn" href="/edit/{escape(pid)}">Back to the draft</a></p></div>"""), 500


@app.route("/logo.png")
def tool_logo():
    """The masthead logo for the tool's own pages, from the file that also
    ships with every galley -- so the tool doesn't depend on an OJS URL."""
    return send_file(Path(__file__).resolve().parent / "logo.png", mimetype="image/png")


# One download button with a zip file: html and xml(s)
# Output is laid out by issue:
#     229/Archival-XML/BCS229-Article-Smith.archival.xml
#     229/HTML/BCS229-Article-Smith.html
#     229/HTML/style.css        <- dependent file of every galley in 229
#     229/HTML/logo.png         <- dependent file of every galley in 229
# Unzip several articles of the same issue and they merge into one 229 folder

def _xslt_path():
    return Path(__file__).resolve().parent / "xslt" / "jats-to-html.xsl"


# The galley HTML references these two by relative name, so they travel with
# it: one copy per issue folder, beside the .html files. In OJS each one is
# uploaded as a DEPENDENT FILE of the HTML galley, with the Name field set to
# exactly the filename below -- style.css as "style.css", logo.png as
# "logo.png". Shipping them also means an unzipped galley opens correctly
# straight off disk, which is how most people check one before it goes up.
GALLEY_DEPENDENT_FILES = ("style.css", "logo.png")


def _dependent_entries(issue):
    """(name-in-zip, bytes) for the galley's dependent files. Added once per
    issue folder -- _zip_response numbers duplicate
    names, and "style-1.css" would not load."""
    root = Path(__file__).resolve().parent
    out = []
    for name in GALLEY_DEPENDENT_FILES:
        src = root / name
        try:
            out.append((f"{issue}/HTML/{name}", src.read_bytes()))
        except Exception as e:
            out.append((f"{issue}/HTML/{name}-NOT-INCLUDED.txt",
                        (f"{name} could not be added to this zip: {e}\n\n"
                         f"The galley HTML references it by name, so put a copy "
                         f"of {name} beside the .html files before opening one, "
                         f"and upload it to OJS as a dependent file of the HTML "
                         f"galley named exactly \"{name}\".\n").encode("utf-8")))
    return out


def _bundle_entries(project):
    """(name-in-zip, bytes) for one article. Never raises -- a step that fails
    leaves a short note in the zip instead so the rest still downloads."""
    issue = issue_slug(project)
    base = project_basename(project)
    out = []
    xml = None

    # The HTML galley is built from the lens-profile XML (the path every
    # draft has been tested on). That XML is not put in the zip: BC Studies
    # does not upload XML to OJS.
    try:
        xml = render_project(project, LENS)[0]
    except Exception as e:
        out.append((f"{issue}/HTML/{base}-NOT-BUILT.txt",
                    f"The HTML copy could not be built: {e}\n".encode("utf-8")))

    try:
        out.append((f"{issue}/Archival-XML/{base}.archival.xml",
                    render_project(project, ARCHIVAL)[0].encode("utf-8")))
    except Exception as e:
        out.append((f"{issue}/Archival-XML/{base}-NOT-BUILT.txt",
                    f"The archival copy could not be built: {e}\n".encode("utf-8")))

    if xml is not None:
        try:
            xsl = _xslt_path()
            if not xsl.exists():
                raise FileNotFoundError("xslt/jats-to-html.xsl is missing")
            out.append((f"{issue}/HTML/{base}.html",
                        transform_xml_with_xslt(xml, xsl).encode("utf-8")))
            out.extend(_media_entries(project))
        except Exception as e:
            out.append((f"{issue}/HTML/{base}-NOT-BUILT.txt",
                        f"The HTML copy could not be built: {e}\n".encode("utf-8")))
    return out


def _zip_response(entries, zip_name):
    seen = {}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for arcname, data in entries:
            # two drafts can share a filename (same issue, section and author); number them
            if arcname in seen:
                seen[arcname] += 1
                stem, dot, ext = arcname.rpartition(".")
                arcname = f"{stem}-{seen[arcname]}{dot}{ext}" if dot else f"{arcname}-{seen[arcname]}"
            else:
                seen[arcname] = 1
            z.writestr(arcname, data)
    buf.seek(0)
    return send_file(buf, as_attachment=True, mimetype="application/zip",
                     download_name=zip_name)


@app.route("/download_all/<pid>")
def download_all(pid):
    """Everything for one article."""
    try:
        project = load_project(pid)
    except Exception:
        return redirect("/?error=Could+not+open+that+draft.")
    project["id"] = pid
    entries = _bundle_entries(project) + _dependent_entries(issue_slug(project))
    return _zip_response(entries, f"{project_basename(project)}-files.zip")


@app.route("/download_issue/<issue>")
def download_issue(issue):
    """Everything for every draft in one issue."""
    want = issue_slug({"meta": {"issue_number": issue}}).lower()
    entries, folder, n = [], None, 0
    for row in list_projects():
        try:
            project = load_project(row["id"])
        except Exception:
            continue
        project["id"] = row["id"]
        slug = issue_slug(project)
        if slug.lower() != want:
            continue
        folder = folder or slug
        entries.extend(_bundle_entries(project))
        n += 1
    if not n:
        return redirect("/?error=No+drafts+found+for+that+issue.")
    entries.extend(_dependent_entries(folder))
    return _zip_response(entries, f"BCS{folder}-files.zip")


# =============================================================================
# THE EDITOR PAGE
# =============================================================================

EDITOR_CSS = """
  /* small caps and special-character runs carried over from InDesign; the
     dotted underline shows where a word will get the special-character font */
  .ed span.sc, .prev span.sc { font-variant: small-caps; }
  .ed span[data-style-type], .prev span[data-style-type] { text-decoration: underline dotted #6b7c93; text-underline-offset: 3px; }
  .tabs { display: flex; gap: 4px; margin: 18px 0 0; flex-wrap: wrap; }
  .tabs button { background: #dde3ec; color: #333; border-radius: 8px 8px 0 0; padding: 9px 18px; }
  .tabs button.active { background: white; color: #1F3864; font-weight: 700; }
  .panel { background: white; border: 1px solid #dfe3e8; border-radius: 0 8px 8px 8px; padding: 18px 22px; display: none; }
  .panel.active { display: block; }
  .savebar { position: fixed; top: 8px; right: 20px; z-index: 10; display: flex; gap: 10px; align-items: center; }
  .savebar .status { color: #27422B; font-size: .85rem; background: #ffffff; border: 1px solid #dfe3e8; border-radius: 6px; padding: 4px 10px; }
  #savestatus { color: #000000; font-size: .85rem; background: #ffffff; border: 1px solid #dfe3e8; border-radius: 6px; padding: 4px 10px; }
  .ed.ed1 { white-space: nowrap; overflow-x: auto; min-height: 1.2em; padding: 5px 8px; }
  .ed { border: 1px solid #d6dbe3; border-radius: 5px; padding: 8px 10px; min-height: 1.5em; background: #fff; font-size: .95rem; line-height: 1.5; }
  .ed:focus { outline: 2px solid #7f9fd4; }
  .block { display: grid; grid-template-columns: 150px 1fr 96px; gap: 8px; margin: 7px 0; align-items: start; border-radius: 6px; }
  .block select { width: 100%; padding: 6px 4px; border-radius: 5px; border: 1px solid #ccc; font-size: .82rem; }
  .block .bbtns { display: flex; gap: 2px; flex-wrap: wrap; }
  .block .bbtns button { padding: 3px 7px; font-size: .78rem; background: #eef1f6; color: #333; }
  .block.k-heading .ed { font-weight: 700; font-size: 1.05rem; background: #f6f8fc; }
  .block.k-blockquote .ed { margin-left: 20px; font-style: normal; background: #fafafa; border-left: 3px solid #c9d4e8; }
  .block.k-verse .ed { margin-left: 20px; }
  .block.k-verse-break .ed { display: none; }
  .figfields { display: grid; gap: 5px; margin-bottom: 6px; padding: 8px; background: #f6f8fc; border: 1px solid #dbe3f0; border-radius: 6px; }
  .figfields label { font-size: .72rem; color: #556; font-weight: 600; display: block; margin-bottom: 2px; }
  .figfields input { width: 100%; padding: 5px 6px; border: 1px solid #ccc; border-radius: 5px; font-size: .82rem; box-sizing: border-box; }
  .figfields .hint { font-size: .72rem; color: #777; margin: 0; }
  .audrow { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .audrow input.aud-file, .audrow input.fig-file { flex: 1; min-width: 180px; }
  .audrow .audstatus { font-size: .72rem; }
  .audrow .audstatus.ok { color: #1a7f37; }
  .audrow .audstatus.missing { color: #b42318; }
  .figfields audio { width: 100%; height: 34px; }
  .figfields .figthumb { max-width: 220px; max-height: 160px; object-fit: contain; border: 1px solid #dbe3f0; background: #fff; }
  .block.k-audio .ed { min-height: 2.2em; }
  .block.k-audio .ed:empty::before { content: attr(data-ph); color: #aaa; }
  .block.k-figure .ed { min-height: 2.2em; }
  .block .bbtns .drag, .notecard .drag { cursor: grab; user-select: none; font-size: 1rem; line-height: 1; padding: 3px 7px; background: #eef1f6; border-radius: 6px; color: #556; }
  .block .bbtns .moveto { width: 100%; }
  .block.dragging, .notecard.dragging { opacity: .45; }
  .block.drop-before, .notecard.drop-before { box-shadow: 0 -3px 0 #2f5d8a; }
  .block.drop-after, .notecard.drop-after { box-shadow: 0 3px 0 #2f5d8a; }
  .notecard.flash { background: #fff3c4; transition: background .6s; }
  .block.flash { background: #fff3c4; transition: background .6s; }
  .block.k-table .ed:empty::before, .tbl-foot:empty::before { content: attr(data-ph); color: #aaa; }
  .tblfields { display: grid; gap: 6px; padding: 8px; background: #f6f8fc; border: 1px solid #dbe3f0; border-radius: 6px; }
  .tblfields label { font-size: .72rem; color: #556; font-weight: 600; margin: 2px 0 0; }
  .tblmeta { display: grid; grid-template-columns: 1fr 110px 1fr; gap: 8px; align-items: end; }
  .tblmeta input { width: 100%; padding: 5px 6px; border: 1px solid #ccc; border-radius: 5px; font-size: .82rem; }
  .tblmeta .figid { margin: 0 0 6px; }
  .tbltools { display: flex; gap: 4px; flex-wrap: wrap; align-items: center; }
  .tbltools button { padding: 3px 9px; font-size: .78rem; background: #e3e9f2; color: #1f3b5b; }
  .tbltools .hint { font-size: .72rem; }
  .tblscroll { overflow-x: auto; }
  table.tgrid { border-collapse: collapse; width: 100%; background: #fff; }
  table.tgrid td, table.tgrid th { border: 1px solid #c9d4e8; padding: 0; vertical-align: top; font-size: .88rem; font-weight: normal; text-align: left; }
  table.tgrid th { background: #eef2f8; }
  table.tgrid tr.hrow th { background: #dde6f3; font-weight: 700; }
  table.tgrid .ced { padding: 4px 6px; min-height: 1.4em; outline: none; }
  table.tgrid .cur { outline: 2px solid #7f9fd4; outline-offset: -2px; }
  table.tgrid.mini td { padding: 3px 6px; font-size: .78rem; }
  .toolbar.toolbar2 { top: 44px; background: #f3f7fc; border-color: #d6e0ee; }
  .toolbar-hint { margin: -4px 0 8px; }
  .modal .box.wide { max-width: 820px; }
  .mvq { margin-bottom: 8px; }
  .mvlist { max-height: 55vh; overflow: auto; }
  .modal .mvpick { display: grid; grid-template-columns: 38px 110px 1fr auto; gap: 8px; align-items: baseline; font-size: .84rem; padding: 6px 8px; margin: 3px 0; }
  .mvpick .mvn { color: #667; font-size: .75rem; text-align: right; }
  .mvpick .mvk { color: #2c4a68; font-size: .75rem; font-weight: 600; }
  .mvpick.hit { background: #e3f3e3; }
  .mention { background: #2e7d32; color: #fff; border-radius: 10px; padding: 1px 8px; font-size: .7rem; white-space: nowrap; }
  .cand { border: 1px solid #dde3ee; border-radius: 6px; padding: 8px 10px; margin: 8px 0; }
  .cand > div { display: flex; gap: 10px; align-items: center; margin-bottom: 6px; }
  .cand button { margin-left: auto; }
  .planrow { display: flex; gap: 10px; align-items: flex-start; font-size: .86rem; font-weight: normal; color: #1f2937; padding: 7px 4px; border-bottom: 1px solid #eee; margin: 0; }
  .planrow input { margin-top: 4px; }
  .prevtable { margin: 14px 0; }
  .prevtable table td, .prevtable table th { border: 1px solid #dfe3e8; padding: 4px 8px; font-size: .9rem; vertical-align: top; }
  .block.k-figure .ed:empty::before { content: attr(data-ph); color: #aaa; }
  cite { background: #fff3c4; border-radius: 3px; padding: 0 2px; font-style: normal; }
  cite[data-status="confirmed"] { background: #d3f0d3; }
  cite[data-status="none"] { background: #ffd9d9; }
  sup[data-fn] { color: #1F3864; font-weight: 700; }
  a.figref { background: #dbeafe; color: #12408a; border-radius: 3px; padding: 0 2px; text-decoration: none; cursor: text; }
  .figid { font-size: .72rem; color: #667; }
  .figid code { background: #eef1f6; border-radius: 3px; padding: 0 4px; }
  .modal { position: fixed; inset: 0; background: #0006; display: flex; align-items: center; justify-content: center; z-index: 50; }
  .modal .box { background: white; border-radius: 8px; padding: 18px 22px; max-width: 560px; width: 90%; max-height: 80vh; overflow: auto; }
  .modal .box h3 { margin: 0 0 4px; }
  .modal .pick { display: block; width: 100%; text-align: left; margin: 6px 0; background: #eef1f6; color: #222; }
  .modal .pick:hover { background: #dbe3f0; }
  .toolbar { position: sticky; top: 0; background: #fffdf5e8; border: 1px solid #e5e0c9; border-radius: 6px; padding: 6px 10px; margin-bottom: 10px; z-index: 5; display: flex; gap: 6px; align-items: center; }
  .toolbar button { background: #eef1f6; color: #333; padding: 4px 12px; font-size: .85rem; }
  .toolbar .hint { margin-left: auto; }
  .citrow { display: grid; grid-template-columns: 1fr 320px 150px; gap: 10px; padding: 9px 6px; border-bottom: 1px solid #eee; align-items: center; }
  .citrow .ctx { font-size: .88rem; color: #444; }
  .citrow .ctx b { background: #fff3c4; font-weight: 600; padding: 0 2px; border-radius: 3px; }
  .citrow select { width: 100%; padding: 5px; border-radius: 5px; border: 1px solid #ccc; font-size: .82rem; }
  .badge { font-size: .72rem; border-radius: 10px; padding: 2px 9px; }
  .b-auto { background: #fff3c4; } .b-confirmed { background: #d3f0d3; } .b-none { background: #ffd9d9; }
  .refrow { display: grid; grid-template-columns: 60px 1fr 92px; gap: 8px; margin: 6px 0; align-items: start; }
  .refrow .rid { font-size: .72rem; color: #888; padding-top: 10px; }
  .refrow .rid .hasdoi { color: #2e7d32; font-weight: 700; }
  .doibox { margin: -2px 0 12px 68px; border-left: 3px solid #9ecf9e; background: #f3f8f3; border-radius: 0 6px 6px 0; padding: 8px 12px; font-size: .84rem; }
  .doibox.weak { border-left-color: #e0b74a; background: #fdf8ec; }
  .doibox .dtitle { font-weight: 600; }
  .doibox .dmeta { color: #555; font-size: .8rem; margin: 2px 0 6px; }
  .doibox .dwhy { color: #777; font-size: .75rem; }
  .doibox button { font-size: .78rem; padding: 3px 10px; margin-right: 6px; }
  .doibox .no { background: #eee; color: #444; }
  .doibox code { background: #fff; border: 1px solid #dfe3ea; border-radius: 3px; padding: 0 4px; }
  .noteN { font-weight: 700; color: #1F3864; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 18px; }
  .grid4 { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 4px 18px; }
  .genout { background: #f6f8fc; border-radius: 6px; padding: 14px 16px; margin-top: 14px; }
  .v-valid { color: #1a7f37; font-weight: 700; } .v-invalid { color: #b00020; font-weight: 700; } .v-skipped { color: #9a6700; font-weight: 700; }
  .prev h2.t { font-size: 1.4rem; margin-bottom: 2px; }
  .prev .by { color: #555; margin-bottom: 18px; }
  .prev blockquote { border-left: 3px solid #c9d4e8; margin-left: 12px; padding-left: 12px; color: #333; }
  .prev .verse { margin-left: 24px; }
  .prev h3 { font-size: 1.1rem; } .prev h4 { font-size: 1rem; }
  .citetip { position: fixed; display: none; z-index: 200; max-width: 420px; background: #fff; border: 1px solid #c9d4e8;
             border-left: 4px solid #2f5d8a; border-radius: 6px; box-shadow: 0 6px 20px #0002; padding: 10px 12px; font-size: .86rem; }
  .citetip .ct-head { margin-bottom: 6px; }
  .citetip .ct-ref { color: #1f2937; line-height: 1.35; }
  .citetip .ct-ref.none { color: #8a5a00; font-style: italic; }
  .citetip .ct-doi { color: #2e7d32; font-size: .78rem; margin-top: 3px; }
  .citetip .ct-basis { color: #556; font-size: .78rem; font-style: italic; margin-top: 5px; }
  .citetip .ct-btns { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 9px; }
  .citetip .ct-btns button { font-size: .78rem; padding: 3px 10px; margin: 0; }
  .citetip .ct-ok { background: #2e7d32; }
  .citetip .ct-ok:hover { background: #24632a; }
  cite[data-rid]:hover { outline: 1px solid #2f5d8a; cursor: help; }
  .citrow.flash { background: #fff8d8; }
  .citebar { position: fixed; left: 50%; transform: translateX(-50%); bottom: 18px; z-index: 210; background: #fff;
             border: 1px solid #c9d4e8; border-left: 4px solid #2f5d8a; border-radius: 6px; box-shadow: 0 6px 20px #0002;
             padding: 8px 12px; font-size: .86rem; width: 680px; max-width: 94vw; }
  .citebar .cb-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .citebar .cb-row + .cb-row { margin-top: 6px; }
  .citebar select { flex: 1 1 280px; min-width: 0; padding: 5px; border-radius: 5px; border: 1px solid #ccc; font-size: .82rem; margin: 0; }
  .citebar button { margin: 0; }
  .citreturn { position: sticky; top: 52px; z-index: 4; background: #eef4fb; border: 1px solid #c9d4e8; border-radius: 6px;
               padding: 6px 10px; margin-bottom: 8px; display: flex; gap: 10px; align-items: center; }
  .biobox { border: 1px solid #dde3ee; border-radius: 6px; padding: 8px 10px; margin: 8px 0; background: #fbfcfe; }
  .biobox .biohead { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }
  .biobox .biohead label { margin: 0; font-weight: 600; }
  .biobox .biohead input { flex: 1 1 240px; width: auto; min-width: 0; margin: 0; }
  .biobox .biohead button { margin: 0; }
  .biomatch { font-size: .8rem; color: #667; }
  .biomatch.ok { color: #1a7f37; }
  .biomatch.bad { color: #b00020; font-weight: 600; }
  .citation-basis { display: inline-block; margin-top: 4px; color: #1F3864; font-size: 0.8rem; font-style: italic; font-weight: 600; }
"""

EDITOR_JS = r"""
const P = window.__PROJECT__;
let dirty = false;
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const escAttr = s => (s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');

function markDirty(){ dirty = true; $('#savestatus').textContent = 'unsaved changes'; }

// ---------- tabs ----------
function showTab(name){
  $$('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  $$('.panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
  if (name === 'citations') renderCitations();
  if (name === 'preview') renderPreview();
}

// ---------- metadata ----------
const METAFIELDS = [
  ['title','Article title'], ['subtitle','Subtitle (blank if none)'],
  ['authors','Author(s) — separate several with “ and ”'],
  ['orcids','ORCID(s) — one per author in the same order, separate with “ and ” (use “-” for an author without one)'],
  ['section','Section'], ['doi','DOI (blank if none yet)'],
  ['fpage','First page'], ['lpage','Last page'],
  ['issue_number','Issue number'], ['year','Year'], ['season','Season (blank if none)'],
  ['short_title','Short title (running head) — the heading on a book review; blank uses the title up to its colon'],
  ['issue_editors','Issue editor(s) — separate several with “ and ”'],
  ['epub_date','Published online — the date it goes up on OJS (YYYY-MM-DD)'],
  ['pdf_url','PDF on OJS — the galley’s “PDF” button links here (blank hides it)'],
  ['article_url','Article page on OJS — the “Share” button uses this only when there is no DOI'],
  ['rights','Rights — “cc” for a Creative Commons article, “copyright” for the journal agreement (blank = journal default)'],
  ['seq','Position in issue (file numbering)'], ['reviewer_affiliation','Reviewer affiliation (book reviews)'],
];
// Title and subtitle take italics and bold, for a book or a court case named in
// them, so they are one-line rich-text boxes rather than plain inputs.
const RICHMETA = new Set(['title', 'subtitle']);
function titleHtml(s){
  // just the words and their italics/bold, for showing a title back on the page
  const d = document.createElement('div'); d.innerHTML = s || '';
  const walk = n => [...n.childNodes].map(c => {
    if (c.nodeType === 3) return escAttr(c.textContent);
    if (c.nodeType !== 1 || c.tagName === 'SUP') return '';
    const inner = walk(c);
    const it = /^(I|EM)$/.test(c.tagName) || c.style.fontStyle === 'italic';
    const bd = /^(B|STRONG)$/.test(c.tagName) || /^(bold|[6-9]00)$/.test(c.style.fontWeight);
    const t = it ? '<i>' + inner + '</i>' : inner;
    return bd ? '<b>' + t + '</b>' : t;
  }).join('');
  return walk(d).replace(/\s+/g, ' ').trim();
}
function richMetaField(d, k, lab){
  d.innerHTML = `<label>${lab}</label><div class="ed ed1" contenteditable="true"></div>`;
  const ed = d.querySelector('.ed');
  ed.innerHTML = P.meta[k] || '';
  const save = () => { P.meta[k] = ed.innerHTML.replace(/(<br\s*\/?>|\s)+$/i, ''); markDirty(); };
  ed.addEventListener('input', save);
  // one line: no paragraph breaks, and pasted text arrives unstyled
  ed.addEventListener('keydown', e => { if (e.key === 'Enter') e.preventDefault(); });
  ed.addEventListener('paste', e => {
    e.preventDefault();
    const text = (e.clipboardData || window.clipboardData).getData('text/plain').replace(/\s+/g, ' ');
    document.execCommand('insertText', false, text);
  });
}
function renderMeta(){
  const c = $('#metafields'); c.innerHTML = '';
  METAFIELDS.forEach(([k, lab]) => {
    const d = document.createElement('div');
    if (RICHMETA.has(k)) { richMetaField(d, k, lab); c.appendChild(d); return; }
    d.innerHTML = `<label>${lab}</label><input type="text" value="${escAttr(String(P.meta[k] ?? ''))}">`;
    d.querySelector('input').addEventListener('input', e => { P.meta[k] = e.target.value; markDirty(); });
    c.appendChild(d);
  });
  $('#kw').value = (P.meta.keywords || []).join('; ');
  $('#kw').addEventListener('input', e => {
    P.meta.keywords = e.target.value.split(';').map(s => s.trim()).filter(Boolean); markDirty();
  });
  renderBios();
  [['abstract','abstract_html'],['bookinfo','book_info_html'],['ack','ack_html'],['funding','funding_html'],['ethics','ethics_html']].forEach(([id, key]) => {
    const ed = $('#meta-' + id);
    ed.innerHTML = P.meta[key] || '';
    ed.addEventListener('input', () => { P.meta[key] = ed.innerHTML; markDirty(); });
  });
}

// ---------- body blocks ----------
const KINDS = [
  ['p','Paragraph'], ['heading:1','Heading'], ['heading:2','Sub-heading'], ['heading:3','Sub-sub-heading'],
  ['blockquote','Block quote'], ['verse','Verse line'], ['verse-break','Stanza break'],
  ['epigraph','Epigraph'], ['epigraph-source','Epigraph source'],
  ['figure','Figure (image)'], ['audio','Audio clip'], ['table','Table'], ['fig-caption','Figure caption (old)'], ['divider','Divider (•)'],
];
function kindValue(b){ return b.kind === 'heading' ? 'heading:' + (b.level || 1) : b.kind; }

// Every figure needs a stable id so in-text references can point at it.
function figureBlocks(){ return P.blocks.filter(b => b.kind === 'figure'); }
function ensureFigIds(){
  const used = new Set(figureBlocks().map(b => b.id).filter(Boolean));
  let n = 0, changed = false;
  figureBlocks().forEach(b => {
    if (b.id) return;
    do { n++; } while (used.has('fig-' + n));
    b.id = 'fig-' + n; used.add(b.id); changed = true;
  });
  return changed;
}
function figLabel(b, i){
  return (b.label || '').trim() || (b.file || '').trim() || ('Figure ' + (i + 1));
}

// Audio clips get stable ids the same way (aud-1, aud-2 ...).
function audioBlocks(){ return P.blocks.filter(b => b.kind === 'audio'); }
function ensureAudIds(){
  const used = new Set(audioBlocks().map(b => b.id).filter(Boolean));
  let n = 0, changed = false;
  audioBlocks().forEach(b => {
    if (b.id) return;
    do { n++; } while (used.has('aud-' + n));
    b.id = 'aud-' + n; used.add(b.id); changed = true;
  });
  return changed;
}
// Filenames already uploaded for this draft (projects/media/<id>/), so each
// audio and figure block can say whether its file will go into the download zip.
let mediaFiles = null;
async function loadMediaList(){
  try { mediaFiles = new Set((await (await fetch('/media_list/' + P.id)).json()).files); }
  catch (e) { mediaFiles = null; }
}
function mediaUrl(name){ return '/media/' + P.id + '/' + encodeURIComponent(name); }
function audioStatus(b){
  const f = (b.file || '').trim();
  if (!f) return ['missing', 'No file yet — upload one or type the filename.'];
  if (!mediaFiles) return ['', ''];
  return mediaFiles.has(f) ? ['ok', '✓ uploaded — goes into the download zip']
                           : ['missing', 'Not uploaded here — the zip will not include it.'];
}
function hasMedia(b){ const f = (b.file || '').trim(); return !!(f && mediaFiles && mediaFiles.has(f)); }
// kind is 'audio' or 'image'; the server checks the file is what it says
async function uploadMedia(b, input, row, kind){
  const file = input.files[0];
  if (!file) return;
  const st = row.querySelector('.audstatus');
  st.className = 'audstatus'; st.textContent = 'Uploading ' + file.name + '…';
  const fd = new FormData(); fd.append('file', file); fd.append('kind', kind);
  try {
    const r = await fetch('/media/' + P.id, {method: 'POST', body: fd});
    const data = await r.json().catch(() => ({ok: false, error: r.status === 413 ? 'File too large (limit 300 MB).' : 'Upload failed.'}));
    if (!data.ok) { st.className = 'audstatus missing'; st.textContent = data.error; return; }
    b.file = data.file;
    if (mediaFiles) mediaFiles.add(data.file);
    markDirty(); renderBlocks(); flashBlocks([b]);
  } catch (e) { st.className = 'audstatus missing'; st.textContent = 'Upload failed — is the server running?'; }
}

function renderBlocks(){
  if (ensureFigIds()) markDirty();
  if (ensureAudIds()) markDirty();
  if (ensureTblIds()) markDirty();
  updateUndoBtn();
  const c = $('#blocks'); c.innerHTML = '';
  P.blocks.forEach((b, i) => c.appendChild(blockRow(b, i)));
  if (!P.blocks.length) {
    const btn = document.createElement('button');
    btn.textContent = '+ Add first paragraph'; btn.className = 'ghost';
    btn.onclick = () => { P.blocks.push({kind:'p', level:1, html:''}); markDirty(); renderBlocks(); };
    c.appendChild(btn);
  }
}
function blockRow(b, i){
  const row = document.createElement('div');
  row.className = 'block k-' + b.kind;
  const opts = KINDS.map(([v, lab]) => `<option value="${v}"${v===kindValue(b)?' selected':''}>${lab}</option>`).join('');
  const [fst, fmsg] = b.kind === 'figure' ? audioStatus(b) : ['', ''];
  const figFields = b.kind === 'figure' ? `<div class="figfields">
      <div><label>Image file (as attached to the HTML galley in OJS)</label>
        <div class="audrow"><input class="fig-file" placeholder="figure1.jpg" value="${escAttr(b.file || '')}">
          <label class="btn small" style="margin:0;color:#fff">Upload image…<input type="file" class="fig-up" accept="image/*,.jpg,.jpeg,.png,.gif,.webp,.svg" hidden></label>
          <span class="audstatus ${fst}">${escapeHtml(fmsg)}</span></div></div>
      ${hasMedia(b) ? `<img class="figthumb" alt="" src="${escAttr(mediaUrl(b.file))}">` : ''}
      <div><label>Label (optional)</label>
        <input class="fig-label" placeholder="Figure 1" value="${escAttr(b.label || '')}"></div>
      <div><label>Alt text — image description for accessibility (optional)</label>
        <input class="fig-alt" placeholder="Pie chart showing poll results" value="${escAttr(b.alt || '')}"></div>
      <p class="figid">Figure ID <code>${escAttr(b.id || '')}</code> — in-text mentions linked to this figure become links that jump to it in the galley.</p>
      <p class="hint">Use a <b>.jpg or .png</b> with no spaces in the name (e.g. <code>fig1.jpg</code>) &mdash; browsers can't show .tif, .eps, .psd or .ai. An uploaded image goes into the download zip beside the HTML. In OJS: upload it as a <b>dependent file</b> of the HTML galley and set its Name to exactly the filename above. Caption text goes in the box below.</p>
    </div>` : '';
  const [ast, amsg] = b.kind === 'audio' ? audioStatus(b) : ['', ''];
  const audFields = b.kind === 'audio' ? `<div class="figfields">
      <div><label>Audio file (as attached to the HTML galley in OJS)</label>
        <div class="audrow"><input class="aud-file" placeholder="hot-topic-episode-1.mp3" value="${escAttr(b.file || '')}">
          <label class="btn small" style="margin:0;color:#fff">Upload audio…<input type="file" class="aud-up" accept="audio/*,.mp3,.m4a,.wav,.ogg" hidden></label>
          <span class="audstatus ${ast}">${escapeHtml(amsg)}</span></div></div>
      ${b.file && mediaFiles && mediaFiles.has(b.file) ? `<audio controls preload="none" src="${escAttr(mediaUrl(b.file))}"></audio>` : ''}
      <div><label>Label (optional)</label>
        <input class="fig-label" placeholder="Episode 1" value="${escAttr(b.label || '')}"></div>
      <div><label>Title (optional)</label>
        <input class="aud-title" placeholder="Living Through the Heat Dome" value="${escAttr(b.caption_title || '')}"></div>
      <p class="figid">Audio ID <code>${escAttr(b.id || '')}</code></p>
      <p class="hint">The galley prints the player at the <b>top of the article</b>, under the journal line and above the abstract, wherever this block sits. MP3 plays everywhere. In OJS: upload this file as a <b>dependent file</b> of the HTML galley and set its Name to exactly the filename above. Description or transcript link goes in the box below.</p>
    </div>` : '';
  row.innerHTML = `<div><select>${opts}</select></div>
    <div>${figFields}${audFields}<div class="ed" contenteditable="true"></div></div>
    <div class="bbtns"><button title="move up">&uarr;</button><button title="move down">&darr;</button>
    <button title="add paragraph below">+</button><button title="delete">&#10005;</button>
    <span class="drag" draggable="true" title="Drag to move this block">&#10303;</span>
    <button class="moveto" title="Move this block to another place">Move to&hellip;</button></div>`;
  const ed = row.querySelector('.ed');
  ed.innerHTML = b.html || '';
  ed.addEventListener('input', () => { b.html = ed.innerHTML; markDirty(); });
  ed.__holder = b;   // so the citation hover card can find its way back
  ed.addEventListener('focus', () => { window.__lastEd = ed; window.__lastBlock = b; });
  if (b.kind === 'figure') {
    const ff = row.querySelector('.fig-file');
    const fl = row.querySelector('.fig-label');
    const fa = row.querySelector('.fig-alt');
    ff.addEventListener('input', () => { b.file = ff.value.trim(); markDirty(); });
    ff.addEventListener('change', () => renderBlocks());
    row.querySelector('.fig-up').addEventListener('change', e => uploadMedia(b, e.target, row, 'image'));
    fl.addEventListener('input', () => { b.label = fl.value; markDirty(); });
    fa.addEventListener('input', () => { b.alt = fa.value; markDirty(); });
    ed.setAttribute('data-ph', 'Caption text (optional)');
  }
  if (b.kind === 'audio') {
    const af = row.querySelector('.aud-file');
    const fl = row.querySelector('.fig-label');
    const at = row.querySelector('.aud-title');
    af.addEventListener('input', () => { b.file = af.value.trim(); markDirty(); });
    af.addEventListener('change', () => renderBlocks());
    fl.addEventListener('input', () => { b.label = fl.value; markDirty(); });
    at.addEventListener('input', () => { b.caption_title = at.value; markDirty(); });
    row.querySelector('.aud-up').addEventListener('change', e => uploadMedia(b, e.target, row, 'audio'));
    ed.setAttribute('data-ph', 'Description of the clip, speakers, or a link to its transcript (optional)');
  }
  if (b.kind === 'table') {
    const te = tableEditor(b, i);
    ed.replaceWith(te);
    te.querySelector('.capslot').replaceWith(ed);   // the caption box sits under the label
    ed.setAttribute('data-ph', 'e.g. Ranks and tenures of RCMP detachment commanders');
  }
  row.querySelector('select').addEventListener('change', e => {
    const v = e.target.value;
    if (b.kind === 'table' && v !== 'table' && !confirm('Turn this table into a ' + e.target.selectedOptions[0].textContent
        + '? The cells stop appearing in the XML (switch it back to Table to get them back); the caption becomes the text.')) {
      e.target.value = 'table'; return;
    }
    if (v === 'table' && b.kind !== 'table') paragraphToTable(b);
    if (v.startsWith('heading:')) { b.kind = 'heading'; b.level = +v.split(':')[1]; }
    else { b.kind = v; }
    markDirty(); renderBlocks();
  });
  const [up, down, add, del] = row.querySelectorAll('.bbtns button');
  up.onclick = () => { if (i>0){ [P.blocks[i-1], P.blocks[i]] = [P.blocks[i], P.blocks[i-1]]; markDirty(); renderBlocks(); } };
  down.onclick = () => { if (i<P.blocks.length-1){ [P.blocks[i+1], P.blocks[i]] = [P.blocks[i], P.blocks[i+1]]; markDirty(); renderBlocks(); } };
  add.onclick = () => { P.blocks.splice(i+1, 0, {kind:'p', level:1, html:''}); markDirty(); renderBlocks(); };
  del.onclick = () => { if (confirm('Delete this block?')){ P.blocks.splice(i,1); markDirty(); renderBlocks(); } };
  row.querySelector('.moveto').onclick = () => openMoveTo(b);
  wireDrag(row, b, P.blocks, moveBlock);
  row.__block = b;
  row.addEventListener('focusin', () => { window.__lastBlockRow = b; });
  return row;
}

// toolbar
function fmt(cmd){ document.execCommand('styleWithCSS', false, false); document.execCommand(cmd); }
function markCitation(){
  const sel = window.getSelection();
  if (!sel.rangeCount || sel.isCollapsed) { alert('Select the citation text first (e.g. “Pinder 477” or “26”), then click this button.'); return; }
  const range = sel.getRangeAt(0);
  const cite = document.createElement('cite');
  cite.dataset.rid = ''; cite.dataset.status = 'none'; cite.dataset.basis = 'manual';
  try { range.surroundContents(cite); } catch (e) {
    alert('Could not mark that selection — select text within a single formatting run (avoid crossing italics boundaries).');
    return;
  }
  sel.removeAllRanges();
  if (window.__lastEd && window.__lastBlock) { window.__lastBlock.html = window.__lastEd.innerHTML; }
  markDirty();
}

// ---------- in-text figure references ----------
// A marked mention becomes <xref ref-type="fig" rid="fig-1"> in the XML, which
// the HTML galley turns into a link that jumps to the figure.
function syncLastEd(){
  if (window.__lastEd && window.__lastBlock) window.__lastBlock.html = window.__lastEd.innerHTML;
}
function closestFigref(node){
  while (node && node !== document) {
    if (node.nodeType === 1 && node.tagName === 'A' && node.dataset.fig) return node;
    node = node.parentNode;
  }
  return null;
}
function linkFigure(){
  const sel = window.getSelection();
  if (!sel.rangeCount) { alert('Click in the text first.'); return; }
  const range = sel.getRangeAt(0);
  const existing = closestFigref(range.startContainer);
  const figs = figureBlocks();
  if (!figs.length && !existing) {
    alert('This article has no Figure (image) blocks yet. Add one in the Body tab first, then come back and link the mention to it.');
    return;
  }
  if (sel.isCollapsed && !existing) {
    alert('Select the words that mention the figure (e.g. “Figure 1” or “see fig. 2”), then click this button.');
    return;
  }
  const saved = range.cloneRange();
  const box = document.createElement('div');
  box.className = 'modal';
  const opts = figs.map((b, i) =>
      `<button class="pick" data-fig="${escAttr(b.id)}">${escapeHtml(figLabel(b, i))}
        <span class="hint"> — ${escapeHtml(b.file || 'no image file')} (${escAttr(b.id)})</span></button>`).join('');
  box.innerHTML = `<div class="box"><h3>Link this mention to a figure</h3>
    <p class="hint">The reader can click it in OJS to pull the figure up beside the text.</p>
    ${opts}
    ${existing ? '<button class="pick" data-fig="">✕ Remove this figure link</button>' : ''}
    <p style="margin-top:14px"><button class="ghost" data-cancel="1">Cancel</button></p></div>`;
  box.addEventListener('click', e => {
    if (e.target === box || (e.target.dataset && e.target.dataset.cancel)) { box.remove(); return; }
    const btn = e.target.closest('button.pick');
    if (!btn) return;
    box.remove();
    if (btn.dataset.fig === '') {
      existing.replaceWith(...existing.childNodes);
    } else {
      if (existing) existing.replaceWith(...existing.childNodes);
      const a = document.createElement('a');
      a.className = 'figref'; a.dataset.fig = btn.dataset.fig;
      try { saved.surroundContents(a); }
      catch (err) {
        alert('Could not mark that selection — select text inside a single formatting run (avoid crossing italics or citation boundaries).');
        return;
      }
      window.getSelection().removeAllRanges();
    }
    syncLastEd(); markDirty(); renderBlocks(); renderNotes();
  });
  document.body.appendChild(box);
}

// Bulk pass: wrap every "Figure 3" / "fig. 3" mention that isn't linked yet.
function autoLinkFigures(){
  const figs = figureBlocks();
  if (!figs.length) { alert('This article has no Figure (image) blocks yet.'); return; }
  const byNumber = {};
  figs.forEach((b, i) => {
    const m = /(\d+)\s*$/.exec((b.label || '').trim());
    byNumber[m ? m[1] : String(i + 1)] = b.id;
  });
  // Sub-figures (1a, 1b, 1a–c, 1(a)) link to the parent figure 1.
  const RE = /\b(?:figs?\.|figures?|fig)\s*(\d+)(?:[a-z](?:\s*[-–]\s*[a-z])?|\([a-z]\))?(?![\w(])/gi;
  let n = 0;
  const holders = P.blocks.filter(b => ['p','blockquote','epigraph','figure'].includes(b.kind))
                   .concat(...P.notes.map(x => x.parts));
  holders.forEach(holder => {
    const dom = document.createElement('div');
    dom.innerHTML = holder.html || '';
    let changed = false;
    const walker = document.createTreeWalker(dom, NodeFilter.SHOW_TEXT);
    const texts = []; while (walker.nextNode()) texts.push(walker.currentNode);
    texts.forEach(node => {
      if (closestFigref(node.parentNode)) return;         // already linked
      const s = node.nodeValue; RE.lastIndex = 0;
      let m, last = 0; const frag = document.createDocumentFragment();
      while ((m = RE.exec(s))) {
        const id = byNumber[m[1]];
        if (!id) continue;
        frag.appendChild(document.createTextNode(s.slice(last, m.index)));
        const a = document.createElement('a');
        a.className = 'figref'; a.dataset.fig = id; a.textContent = m[0];
        frag.appendChild(a); last = m.index + m[0].length; n++; changed = true;
      }
      if (last) { frag.appendChild(document.createTextNode(s.slice(last))); node.replaceWith(frag); }
    });
    if (changed) holder.html = dom.innerHTML;
  });
  markDirty(); renderBlocks(); renderNotes();
  alert(n ? n + ' figure mention(s) linked. Check in the Body tab (blue highlight).'
          : 'No unlinked “Figure N” mentions found. Select the text and use “Link to figure” to mark one by hand.');
}

// ---------- tables ----------
// A table block keeps its caption in b.html (like a figure) and its grid in
// b.rows: [[{html, th, colspan, rowspan}]]. The first b.header_rows rows are
// the table head. b.foot_html is the source/notes line under the table.
function tableBlocks(){ return P.blocks.filter(b => b.kind === 'table'); }
function ensureTblIds(){
  const used = new Set(tableBlocks().map(b => b.id).filter(Boolean));
  let n = 0, changed = false;
  tableBlocks().forEach(b => {
    if (!b.rows) { b.rows = [[newCell(), newCell()], [newCell(), newCell()]]; changed = true; }
    if (b.id) return;
    do { n++; } while (used.has('tbl-' + n));
    b.id = 'tbl-' + n; used.add(b.id); changed = true;
  });
  return changed;
}
function newCell(){ return {html:'', th:false, colspan:1, rowspan:1}; }
function newTableBlock(nrows, ncols){
  const rows = [];
  for (let r = 0; r < nrows; r++) { const row = []; for (let c = 0; c < ncols; c++) row.push(newCell()); rows.push(row); }
  return {kind:'table', level:1, id:'', label:'', html:'', header_rows:1, rows, foot_html:''};
}
const span = (cell, k) => Math.max(1, parseInt(cell[k], 10) || 1);

// Where every cell sits once row and column spans are laid out.
// occ[r][c] is the cell covering that slot; pos maps a cell to its top-left slot.
function tableLayout(b){
  const occ = [], pos = new Map();
  b.rows.forEach((row, r) => {
    occ[r] = occ[r] || [];
    let c = 0;
    row.forEach(cell => {
      while (occ[r][c]) c++;
      pos.set(cell, {r, c});
      for (let dr = 0; dr < span(cell,'rowspan'); dr++) {
        occ[r+dr] = occ[r+dr] || [];
        for (let dc = 0; dc < span(cell,'colspan'); dc++) occ[r+dr][c+dc] = cell;
      }
      c += span(cell,'colspan');
    });
  });
  const ncols = Math.max(0, ...occ.map(x => x ? x.length : 0));
  return {occ, pos, ncols};
}
function tblInsertRow(b, after){            // after = row index; -1 inserts at the top
  const {occ, pos, ncols} = tableLayout(b);
  const row = [];
  for (let c = 0; c < ncols; c++) {
    const above = after >= 0 && occ[after] && occ[after][c];
    if (above) {
      const p = pos.get(above);
      if (p.r + span(above,'rowspan') - 1 > after) {        // a tall cell runs through the new row
        if (p.c === c) above.rowspan = span(above,'rowspan') + 1;
        continue;
      }
    }
    row.push(newCell());
  }
  b.rows.splice(after + 1, 0, row);
  if (after < (+b.header_rows || 0) - 1) b.header_rows = (+b.header_rows || 0) + 1;
}
function tblDeleteRow(b, r){
  const {occ, pos, ncols} = tableLayout(b);
  const next = b.rows[r+1] || [], moves = [];
  for (let c = 0; c < ncols; c++) {
    const cell = occ[r] && occ[r][c];
    if (!cell) continue;
    const p = pos.get(cell);
    if (p.c !== c || span(cell,'rowspan') === 1) continue;
    cell.rowspan = span(cell,'rowspan') - 1;
    if (p.r === r) moves.push({cell, idx: next.filter(x => pos.get(x).c < c).length});   // slides down a row
  }
  b.rows.splice(r, 1);
  moves.forEach((m, k) => { if (b.rows[r]) b.rows[r].splice(m.idx + k, 0, m.cell); });
  if (r < (+b.header_rows || 0)) b.header_rows = (+b.header_rows) - 1;
}
function tblInsertCol(b, after){            // after = column index; -1 inserts at the left
  const {occ, pos} = tableLayout(b);
  b.rows.forEach((row, r) => {
    const left = after >= 0 && occ[r] && occ[r][after];
    if (left) {
      const p = pos.get(left);
      if (p.c + span(left,'colspan') - 1 > after) {          // a wide cell runs through the new column
        if (p.r === r) left.colspan = span(left,'colspan') + 1;
        return;
      }
    }
    row.splice(row.filter(x => pos.get(x).c <= after).length, 0, newCell());
  });
}
function tblDeleteCol(b, c){
  const {occ, pos} = tableLayout(b);
  const seen = new Set();
  b.rows.forEach((row, r) => {
    const cell = occ[r] && occ[r][c];
    if (!cell || seen.has(cell)) return;
    seen.add(cell);
    if (span(cell,'colspan') > 1) { cell.colspan = span(cell,'colspan') - 1; return; }
    const home = b.rows[pos.get(cell).r];
    home.splice(home.indexOf(cell), 1);
  });
}
function tblMergeRight(b, cell){
  const {occ, pos} = tableLayout(b);
  const p = pos.get(cell);
  const right = occ[p.r] && occ[p.r][p.c + span(cell,'colspan')];
  if (!right || pos.get(right).r !== p.r || span(right,'rowspan') !== span(cell,'rowspan')) {
    alert('There is no cell of the same height to the right of this one to merge with.'); return false;
  }
  if ((right.html || '').trim()) cell.html = ((cell.html || '').trim() + ' ' + right.html).trim();
  cell.colspan = span(cell,'colspan') + span(right,'colspan');
  const row = b.rows[p.r]; row.splice(row.indexOf(right), 1);
  return true;
}
function tblSplit(b, cell){
  const cs = span(cell,'colspan'), rs = span(cell,'rowspan');
  if (cs === 1 && rs === 1) { alert('This cell is not merged.'); return false; }
  const {pos} = tableLayout(b);
  const p = pos.get(cell);
  const idxBelow = [];
  for (let dr = 1; dr < rs; dr++) {
    const row = b.rows[p.r + dr] || [];
    idxBelow.push(row.filter(x => pos.get(x).c < p.c).length);
  }
  cell.colspan = 1; cell.rowspan = 1;
  const row0 = b.rows[p.r];
  for (let k = 1; k < cs; k++) row0.splice(row0.indexOf(cell) + 1, 0, newCell());
  idxBelow.forEach((idx, dr) => {
    const row = b.rows[p.r + dr + 1]; if (!row) return;
    for (let k = 0; k < cs; k++) row.splice(idx, 0, newCell());
  });
  return true;
}

// Lines of a pasted or typed table -> rows of cells. Tabs separate cells.
function rowsFromLines(lines){
  const rows = lines.map(line => line.replace(/^\t(?=\S)/, '').split('\t'));
  const ncols = Math.max(1, ...rows.map(r => r.length));
  return rows.map(r => {
    const cells = r.map(h => ({html: cleanCellHtml(h), th:false, colspan:1, rowspan:1}));
    while (cells.length < ncols) cells.push(newCell());
    return cells;
  });
}
function cleanCellHtml(h){ const d = document.createElement('div'); d.innerHTML = h; return d.innerHTML.trim(); }
function htmlLines(html){
  return (html || '').split(/<br\s*\/?>|<\/?(?:p|div)[^>]*>/i).filter(x => x.replace(/<[^>]+>/g, '').trim());
}
function paragraphToTable(b){
  if (b.rows && b.rows.length) return;                  // switching back: keep the old grid
  const lines = htmlLines(b.html);
  if (lines.length && lines.some(l => /\S\t+\S/.test(l))) {
    b.rows = rowsFromLines(lines); b.html = '';
  } else {
    b.rows = newTableBlock(3, 3).rows;                  // the text becomes the caption
  }
  b.header_rows = b.header_rows || 0; b.foot_html = b.foot_html || ''; b.label = b.label || '';
}

function tableEditor(b, i){
  const wrap = document.createElement('div');
  wrap.className = 'tblfields';
  wrap.innerHTML = `<div class="tblmeta">
      <div><label>Label</label><input class="tbl-label" placeholder="Table 1" value="${escAttr(b.label || '')}"></div>
      <div><label>Header rows</label><input class="tbl-head" type="number" min="0" value="${+b.header_rows || 0}"></div>
      <p class="figid">Table ID <code>${escAttr(b.id || '')}</code></p>
    </div>
    <label>Caption — the table’s title (optional)</label>
    <div class="capslot"></div>
    <div class="tbltools">
      <button data-t="row+" title="Insert a row below the selected cell">+ Row</button>
      <button data-t="row-" title="Delete the selected cell’s row">− Row</button>
      <button data-t="col+" title="Insert a column right of the selected cell">+ Column</button>
      <button data-t="col-" title="Delete the selected cell’s column">− Column</button>
      <button data-t="merge" title="Merge the selected cell with the one to its right">Merge →</button>
      <button data-t="split" title="Undo a merge on the selected cell">Split</button>
      <button data-t="th" title="Show the selected cell as a heading cell (e.g. a row label or a sub-head row)">Heading cell</button>
      <button data-t="paste" title="Paste rows copied from Word, Excel or tabbed text">Paste rows…</button>
      <span class="hint tblsel">Click a cell, then use the buttons. Tab moves to the next cell.</span>
    </div>
    <div class="tblscroll"><table class="tgrid"></table></div>
    <label>Source / notes under the table (optional)</label>
    <div class="ed tbl-foot" contenteditable="true" data-ph="Source: …"></div>`;
  const fl = wrap.querySelector('.tbl-label'), fh = wrap.querySelector('.tbl-head');
  fl.addEventListener('input', () => { b.label = fl.value; markDirty(); });
  fh.addEventListener('input', () => { b.header_rows = Math.max(0, parseInt(fh.value, 10) || 0); markDirty(); draw(); });
  const foot = wrap.querySelector('.tbl-foot');
  foot.innerHTML = b.foot_html || '';
  foot.addEventListener('input', () => { b.foot_html = foot.innerHTML; markDirty(); });
  foot.addEventListener('focus', () => { window.__lastEd = foot; window.__lastBlock = {set html(v){ b.foot_html = v; }}; });
  let cur = null;
  function draw(focusCell){
    const t = wrap.querySelector('table.tgrid'); t.innerHTML = '';
    const hr = +b.header_rows || 0;
    b.rows.forEach((row, r) => {
      const tr = t.insertRow();
      if (r < hr) tr.className = 'hrow';
      row.forEach(cell => {
        const td = document.createElement(r < hr || cell.th ? 'th' : 'td');
        if (span(cell,'colspan') > 1) td.colSpan = span(cell,'colspan');
        if (span(cell,'rowspan') > 1) td.rowSpan = span(cell,'rowspan');
        const ed = document.createElement('div');
        ed.className = 'ced'; ed.contentEditable = 'true'; ed.innerHTML = cell.html || '';
        ed.__holder = cell;
        ed.addEventListener('input', () => { cell.html = ed.innerHTML; markDirty(); });
        ed.addEventListener('focus', () => {
          window.__lastEd = ed; window.__lastBlock = cell; cur = cell;
          t.querySelectorAll('.cur').forEach(x => x.classList.remove('cur')); td.classList.add('cur');
        });
        td.appendChild(ed); tr.appendChild(td);
        if (cell === focusCell) setTimeout(() => ed.focus(), 0);
      });
    });
  }
  function where(){
    if (cur && tableLayout(b).pos.has(cur)) return tableLayout(b).pos.get(cur);
    return null;
  }
  wrap.querySelector('.tbltools').addEventListener('click', e => {
    const t = e.target.closest('button'); if (!t) return;
    const act = t.dataset.t, p = where(), lay = tableLayout(b);
    if (act === 'paste') { pasteRows(b, draw); return; }
    if (!p && !['row+','col+'].includes(act)) { alert('Click in a cell first.'); return; }
    if (act === 'row+') tblInsertRow(b, p ? p.r + span(cur,'rowspan') - 1 : b.rows.length - 1);
    else if (act === 'row-') {
      if (b.rows.length <= 1) { alert('A table needs at least one row. Delete the whole block instead.'); return; }
      tblDeleteRow(b, p.r); cur = null;
    }
    else if (act === 'col+') tblInsertCol(b, p ? p.c + span(cur,'colspan') - 1 : lay.ncols - 1);
    else if (act === 'col-') {
      if (lay.ncols <= 1) { alert('A table needs at least one column. Delete the whole block instead.'); return; }
      tblDeleteCol(b, p.c); cur = null;
    }
    else if (act === 'merge') { if (!tblMergeRight(b, cur)) return; }
    else if (act === 'split') { if (!tblSplit(b, cur)) return; }
    else if (act === 'th') cur.th = !cur.th;
    fh.value = +b.header_rows || 0;
    markDirty(); draw(cur);
  });
  draw();
  return wrap;
}

function pasteRows(b, redraw){
  const box = document.createElement('div');
  box.className = 'modal';
  box.innerHTML = `<div class="box"><h3>Paste rows</h3>
    <p class="hint">Copy the table from Word, Excel, Google Sheets or the PDF and paste it here.
    Each line becomes a row; tabs separate the cells.</p>
    <textarea rows="10" style="width:100%;font-family:monospace;font-size:.82rem" placeholder="Name&#9;Years&#10;Constable William Fraser&#9;1957–58"></textarea>
    <p style="margin-top:10px"><button data-a="replace">Replace the table</button>
    <button class="ghost" data-a="append">Add below the last row</button>
    <button class="ghost" data-a="cancel">Cancel</button></p></div>`;
  const ta = box.querySelector('textarea');
  box.addEventListener('click', e => {
    const a = e.target.dataset && e.target.dataset.a;
    if (e.target === box || a === 'cancel') { box.remove(); return; }
    if (!a) return;
    const lines = ta.value.replace(/\r\n?/g, '\n').split('\n').filter(l => l.trim());
    if (!lines.length) { alert('Paste some rows first.'); return; }
    const rows = rowsFromLines(lines.map(l => escapeHtml(l)));
    if (a === 'replace') { b.rows = rows; }
    else {
      const n = tableLayout(b).ncols;
      rows.forEach(r => { while (r.length < n) r.push(newCell()); });
      b.rows.push(...rows);
    }
    box.remove(); markDirty(); renderBlocks();
  });
  document.body.appendChild(box);
  ta.focus();
}

function insertTable(){
  const at = P.blocks.indexOf(window.__lastBlockRow);
  const b = newTableBlock(3, 3);
  const i = at >= 0 ? at + 1 : P.blocks.length;
  P.blocks.splice(i, 0, b);
  markDirty(); renderBlocks(); flashBlocks([b]);
}

// ---------- detecting tables typed with tabs ----------
// InDesign text laid out in columns with tabs (rather than set as a table)
// arrives as a run of paragraphs, or one paragraph of lines, with tabs inside.
function tabbedLine(html){
  const t = (html || '').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/^[\t ]+/, '');
  return /\S\t+\S/.test(t);
}
function findTabbedTables(){
  const found = [];
  let run = [];
  const flush = () => { if (run.length >= 2) found.push(run); run = []; };
  P.blocks.forEach(b => {
    if (b.kind !== 'p') { flush(); return; }
    const lines = htmlLines(b.html);
    if (lines.length >= 2 && lines.filter(tabbedLine).length >= 2) {   // one paragraph of tabbed lines
      flush(); found.push([b]); return;
    }
    if (lines.length === 1 && tabbedLine(lines[0])) run.push(b); else flush();
  });
  flush();
  return found;
}
const TABLE_TITLE = /^\s*(table\s+[0-9ivxlc]+[a-z]?)\s*[.:—–-]?\s*(.*)$/i;
function tabbedToTable(run){
  const lines = [];
  run.forEach(b => htmlLines(b.html).forEach(l => lines.push(l)));
  const t = newTableBlock(0, 0);
  t.rows = rowsFromLines(lines); t.header_rows = 0;
  const first = P.blocks.indexOf(run[0]);
  // a "Table 3. Something" paragraph just above is its label and caption
  const prev = P.blocks[first - 1];
  const prevText = prev && prev.kind === 'p' ? prev.html.replace(/<[^>]+>/g, '').trim() : '';
  const m = prevText.length < 250 && TABLE_TITLE.exec(prevText);
  let start = first;
  if (m) { t.label = m[1]; t.html = escapeHtml(m[2]); start = first - 1; }
  P.blocks.splice(start, first - start + run.length, t);
  return t;
}
function openFindTables(){
  const runs = findTabbedTables();
  const box = document.createElement('div');
  box.className = 'modal';
  if (!runs.length) {
    box.innerHTML = `<div class="box"><h3>No tabbed tables found</h3>
      <p class="hint">No paragraphs laid out in columns with tabs. To build a table by hand use “+ Table”,
      or set a paragraph’s type to Table.</p><p><button data-a="cancel">OK</button></p></div>`;
  } else {
    box.innerHTML = `<div class="box wide"><h3>Tables typed with tabs</h3>
      <p class="hint">These paragraphs are laid out in columns with tab characters, the way a table is often typed
      in InDesign. Converting one makes it a real table (one row per line, one cell per tab).</p>
      <div class="cands"></div>
      <p style="margin-top:12px"><button data-a="all">Convert all</button> <button class="ghost" data-a="cancel">Close</button></p></div>`;
    const list = box.querySelector('.cands');
    runs.forEach((run, k) => {
      const lines = []; run.forEach(b => htmlLines(b.html).forEach(l => lines.push(l)));
      const rows = rowsFromLines(lines);
      const n = P.blocks.indexOf(run[0]) + 1;
      const d = document.createElement('div'); d.className = 'cand';
      d.innerHTML = `<div><b>Block ${n}${run.length > 1 ? '–' + (n + run.length - 1) : ''}</b>
        <span class="hint">${rows.length} rows × ${rows[0].length} columns</span>
        <button class="small" data-k="${k}">Convert</button></div>
        <table class="tgrid mini">${rows.slice(0, 3).map(r => '<tr>' + r.map(c => `<td>${c.html}</td>`).join('') + '</tr>').join('')}
        ${rows.length > 3 ? `<tr><td colspan="${rows[0].length}" class="hint">… ${rows.length - 3} more</td></tr>` : ''}</table>`;
      list.appendChild(d);
    });
  }
  box.addEventListener('click', e => {
    const a = e.target.dataset && e.target.dataset.a, k = e.target.dataset && e.target.dataset.k;
    if (e.target === box || a === 'cancel') { box.remove(); return; }
    if (a === 'all' || k !== undefined) {
      snapshotOrder();
      const made = (a === 'all' ? runs : [runs[+k]]).map(tabbedToTable);
      box.remove(); markDirty(); renderBlocks(); flashBlocks(made);
    }
  });
  document.body.appendChild(box);
}

// ---------- moving blocks (figures and tables above all) ----------
let moveUndo = null;
function snapshotOrder(){ moveUndo = P.blocks.slice(); updateUndoBtn(); }
function updateUndoBtn(){ const u = $('#undomove'); if (u) u.disabled = !moveUndo; }
function undoMove(){
  if (!moveUndo) return;
  P.blocks = moveUndo; moveUndo = null; markDirty(); renderBlocks();
}
function moveBlock(b, before){                 // put b just before block `before` (null = at the end)
  if (b === before) return;
  snapshotOrder();
  P.blocks.splice(P.blocks.indexOf(b), 1);
  const at = before ? P.blocks.indexOf(before) : P.blocks.length;
  P.blocks.splice(at, 0, b);
  markDirty(); renderBlocks(); flashBlocks([b]);
}
function flashBlocks(list){
  const rows = [...$('#blocks').children].filter(r => list.includes(r.__block));
  if (!rows.length) return;
  rows[0].scrollIntoView({block:'center'});
  rows.forEach(r => { r.classList.add('flash'); setTimeout(() => r.classList.remove('flash'), 1800); });
}
function blockPlain(b){ const d = document.createElement('div'); d.innerHTML = b.html || ''; return d.textContent.replace(/\s+/g, ' ').trim(); }
function blockSummary(b){
  const kind = (KINDS.find(k => k[0] === kindValue(b)) || [0, b.kind])[1];
  let text = blockPlain(b);
  if (b.kind === 'figure' || b.kind === 'audio') text = [b.label, b.caption_title, b.file, text].filter(Boolean).join(' — ');
  if (b.kind === 'table') text = [b.label, text].filter(Boolean).join(' — ') || '(table)';
  return {kind, text};
}

// drag and drop: grab the ⠿ handle on any block or note. `list` is the array
// the item lives in (a block can only be dropped among blocks, a note among
// notes); move(item, before) puts it in front of `before`, or last for null.
let dragBlock = null, dragList = null;
function wireDrag(row, b, list, move){
  const h = row.querySelector('.drag');
  h.addEventListener('dragstart', e => {
    dragBlock = b; dragList = list; row.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('application/x-bcs-block', '1');
    try { e.dataTransfer.setDragImage(row, 20, 20); } catch (err) {}
  });
  h.addEventListener('dragend', () => {
    dragBlock = null; row.classList.remove('dragging');
    $$('.drop-before, .drop-after').forEach(x => x.classList.remove('drop-before', 'drop-after'));
  });
  row.addEventListener('dragover', e => {
    if (!dragBlock || dragList !== list) return;
    e.preventDefault(); e.dataTransfer.dropEffect = 'move';
    const r = row.getBoundingClientRect(), after = e.clientY > r.top + r.height / 2;
    row.classList.toggle('drop-after', after); row.classList.toggle('drop-before', !after);
  });
  row.addEventListener('dragleave', e => {
    if (!row.contains(e.relatedTarget)) row.classList.remove('drop-before', 'drop-after');
  });
  row.addEventListener('drop', e => {
    if (!dragBlock || dragList !== list) return;
    e.preventDefault();
    const after = row.classList.contains('drop-after');
    row.classList.remove('drop-before', 'drop-after');
    const moving = dragBlock; dragBlock = null;
    if (moving === b) return;
    move(moving, after ? list[list.indexOf(b) + 1] || null : b);
  });
}
// scroll the page while dragging near the top or bottom of the window
document.addEventListener('dragover', e => {
  if (!dragBlock) return;
  if (e.clientY < 70) window.scrollBy(0, -24);
  else if (e.clientY > window.innerHeight - 70) window.scrollBy(0, 24);
});

// "Move to…": pick the paragraph the block should follow
function openMoveTo(b){
  const box = document.createElement('div');
  box.className = 'modal';
  const s = blockSummary(b);
  const mention = objectMentionTest(b);
  box.innerHTML = `<div class="box wide"><h3>Move ${escapeHtml(s.kind)}: ${escapeHtml(s.text.slice(0, 70))}</h3>
    <p class="hint">Click the block it should come <b>after</b>.
    ${mention ? 'Paragraphs that mention it are marked <span class="mention">mentions it</span>.' : ''}</p>
    <input type="text" class="mvq" placeholder="Search the text…">
    <div class="mvlist"></div>
    <p style="margin-top:10px"><button class="ghost" data-a="cancel">Cancel</button></p></div>`;
  const list = box.querySelector('.mvlist');
  const items = [{b:null, i:-1}].concat(P.blocks.map((x, i) => ({b:x, i})));
  function draw(q){
    q = (q || '').toLowerCase();
    list.innerHTML = '';
    items.forEach(({b: x, i}) => {
      if (x === b) return;
      const sm = x ? blockSummary(x) : {kind:'', text:'(the very top, before everything)'};
      if (q && !sm.text.toLowerCase().includes(q)) return;
      const hit = x && mention && mention(x);
      const btn = document.createElement('button');
      btn.className = 'pick mvpick' + (hit ? ' hit' : '');
      btn.innerHTML = `<span class="mvn">${x ? i + 1 : '↑'}</span><span class="mvk">${escapeHtml(sm.kind)}</span>
        <span class="mvt">${escapeHtml(sm.text.slice(0, 160)) || '<i class="hint">(empty)</i>'}</span>
        ${hit ? '<span class="mention">mentions it</span>' : ''}`;
      btn.onclick = () => {
        box.remove();
        moveBlock(b, x ? P.blocks[P.blocks.indexOf(x) + 1] || null : P.blocks[0]);
      };
      list.appendChild(btn);
    });
  }
  box.querySelector('.mvq').addEventListener('input', e => draw(e.target.value));
  box.addEventListener('click', e => {
    if (e.target === box || (e.target.dataset && e.target.dataset.a === 'cancel')) box.remove();
  });
  document.body.appendChild(box);
  draw('');
  box.querySelector('.mvq').focus();
  const firstHit = list.querySelector('.hit');
  if (firstHit) firstHit.scrollIntoView({block:'center'});
}

// ---------- placing figures and tables at their first mention ----------
const TEXT_KINDS = ['p', 'blockquote', 'epigraph', 'verse'];
function objectNumber(b){
  const kind = b.kind;
  const own = (kind === 'figure' ? figureBlocks() : tableBlocks());
  let m = /(\d+)\s*[a-z]?\s*$/i.exec((b.label || '').trim());
  if (!m) m = (kind === 'figure' ? /^\s*fig(?:ure)?\.?\s*(\d+)/i : /^\s*table\s*(\d+)/i).exec(blockPlain(b));
  return m ? m[1] : String(own.indexOf(b) + 1);
}
// A test that says whether a block's text mentions figure/table b
// ("Figure 3", "fig. 3", "Figures 2 and 3", "Table 1"), or null for other blocks.
function objectMentionTest(b){
  if (b.kind !== 'figure' && b.kind !== 'table') return null;
  const num = +objectNumber(b);
  const word = b.kind === 'figure' ? '(?:figs?\\.?|figures?)' : '(?:tables?)';
  const re = new RegExp('\\b' + word + '\\s*((?:\\d+[a-z]?(?:\\s*(?:,|and|&|to|\\u2013|-)\\s*)?)+)', 'gi');
  return x => {
    if (!TEXT_KINDS.includes(x.kind)) return false;
    if (b.kind === 'figure' && b.id && (x.html || '').includes('data-fig="' + b.id + '"')) return true;
    const text = blockPlain(x);
    let m; re.lastIndex = 0;
    while ((m = re.exec(text))) {
      const nums = m[1].match(/\d+/g).map(Number);
      if (nums.includes(num)) return true;
      if (/(to|–|-)/.test(m[1]) && nums.length === 2 && num > nums[0] && num < nums[1]) return true;
    }
    return false;
  };
}
function trailingObjects(){
  // the figures and tables piled up after the last text block, where the
  // IDML import leaves figures
  const out = [];
  for (let i = P.blocks.length - 1; i >= 0; i--) {
    const b = P.blocks[i];
    if (b.kind === 'figure' || b.kind === 'table') out.unshift(b);
    else if (blockPlain(b) || b.kind === 'heading') break;
  }
  return out;
}
function openPlaceAtMention(){
  ensureFigIds(); ensureTblIds();
  const objs = P.blocks.filter(b => b.kind === 'figure' || b.kind === 'table');
  if (!objs.length) { alert('This article has no figures or tables.'); return; }
  const trailing = new Set(trailingObjects());
  const plan = objs.map(b => {
    const test = objectMentionTest(b);
    const target = P.blocks.find(x => x !== b && test(x)) || null;
    return {b, target, on: !!target && trailing.has(b)};
  });
  const box = document.createElement('div');
  box.className = 'modal';
  box.innerHTML = `<div class="box wide"><h3>Place figures and tables at first mention</h3>
    <p class="hint">Each ticked item moves to just after the paragraph that first mentions it
    (“Figure 2”, “fig. 2”, “Table 1”, or a figure link). Items still at the end of the article are ticked;
    ones you have already placed are not.</p>
    <div class="plan"></div>
    <p style="margin-top:12px"><button data-a="go">Move ticked items</button>
    <button class="ghost" data-a="cancel">Cancel</button></p></div>`;
  const list = box.querySelector('.plan');
  plan.forEach((it, k) => {
    const s = blockSummary(it.b);
    const where = it.target
      ? `after block ${P.blocks.indexOf(it.target) + 1}: “${escapeHtml(blockPlain(it.target).slice(0, 110))}…”`
      : '<span class="hint">no mention of “' + (it.b.kind === 'figure' ? 'Figure ' : 'Table ') + objectNumber(it.b) + '” found — use Move to…</span>';
    const d = document.createElement('label');
    d.className = 'planrow';
    d.innerHTML = `<input type="checkbox" data-k="${k}" ${it.on ? 'checked' : ''} ${it.target ? '' : 'disabled'}>
      <span><b>${it.b.kind === 'figure' ? 'Figure' : 'Table'} ${escapeHtml(objectNumber(it.b))}</b>
      <span class="hint">${escapeHtml(s.text.slice(0, 60))}</span><br>→ ${where}</span>`;
    list.appendChild(d);
  });
  box.addEventListener('click', e => {
    const a = e.target.dataset && e.target.dataset.a;
    if (e.target === box || a === 'cancel') { box.remove(); return; }
    if (a !== 'go') return;
    const chosen = [...list.querySelectorAll('input:checked')].map(x => plan[+x.dataset.k]);
    box.remove();
    if (!chosen.length) return;
    snapshotOrder();
    chosen.forEach(it => P.blocks.splice(P.blocks.indexOf(it.b), 1));
    const byTarget = new Map();
    chosen.forEach(it => { if (!byTarget.has(it.target)) byTarget.set(it.target, []); byTarget.get(it.target).push(it.b); });
    byTarget.forEach((list, target) => {
      let at = P.blocks.indexOf(target) + 1;
      // after anything already placed right below the same paragraph
      while (P.blocks[at] && (P.blocks[at].kind === 'figure' || P.blocks[at].kind === 'table')) at++;
      P.blocks.splice(at, 0, ...list);
    });
    markDirty(); renderBlocks(); flashBlocks(chosen.map(it => it.b));
  });
  document.body.appendChild(box);
}

// ---------- notes ----------
function renderNotes(){
  const c = $('#notes'); c.innerHTML = '';
  P.notes.forEach((n, i) => {
    const card = document.createElement('div'); card.className = 'card notecard';
    card.innerHTML = `<span class="noteN">Note ${i+1}</span>
      <span style="float:right"><span class="drag" draggable="true" title="Drag to move this note">&#10303;</span>
      <button class="small ghost" data-a="up">&uarr;</button>
      <button class="small ghost" data-a="down">&darr;</button>
      <button class="small danger" data-a="del">delete note</button></span><div class="parts"></div>
      <button class="small ghost" data-a="addp">+ paragraph</button>
      <button class="small ghost" data-a="addq">+ quotation</button>`;
    const parts = card.querySelector('.parts');
    n.parts.forEach((part, j) => {
      const d = document.createElement('div');
      d.style.margin = '6px 0';
      d.innerHTML = `<div class="ed" contenteditable="true" style="${part.kind==='q'?'margin-left:18px;border-left:3px solid #c9d4e8;':''}"></div>`;
      const ed = d.querySelector('.ed');
      ed.innerHTML = part.html || '';
      ed.addEventListener('input', () => { part.html = ed.innerHTML; noteSug.delete(part); markDirty(); });
      ed.__holder = part;
      ed.addEventListener('focus', () => { window.__lastEd = ed; window.__lastBlock = part; });
      parts.appendChild(d);
      noteDoiBoxes(part).forEach(b => d.appendChild(b));
    });
    card.addEventListener('click', e => {
      const a = e.target.dataset && e.target.dataset.a;
      if (!a) return;
      if (a === 'del') { if (confirm('Delete note ' + (i+1) + '?')) { P.notes.splice(i,1); markDirty(); renderNotes(); } }
      if (a === 'up' && i > 0) { [P.notes[i-1], P.notes[i]] = [P.notes[i], P.notes[i-1]]; markDirty(); renderNotes(); }
      if (a === 'down' && i < P.notes.length-1) { [P.notes[i+1], P.notes[i]] = [P.notes[i], P.notes[i+1]]; markDirty(); renderNotes(); }
      if (a === 'addp') { n.parts.push({kind:'p', html:''}); markDirty(); renderNotes(); }
      if (a === 'addq') { n.parts.push({kind:'q', html:''}); markDirty(); renderNotes(); }
    });
    wireDrag(card, n, P.notes, moveNote);
    c.appendChild(card);
  });
  const btn = document.createElement('button'); btn.className = 'ghost'; btn.textContent = '+ Add note';
  btn.onclick = () => { P.notes.push({parts:[{kind:'p', html:''}]}); markDirty(); renderNotes(); };
  c.appendChild(btn);
}

function moveNote(n, before){
  P.notes.splice(P.notes.indexOf(n), 1);
  const at = before ? P.notes.indexOf(before) : P.notes.length;
  P.notes.splice(at, 0, n);
  markDirty(); renderNotes();
  const card = [...$('#notes').children][P.notes.indexOf(n)];
  if (card) { card.classList.add('flash'); setTimeout(() => card.classList.remove('flash'), 1800); }
}

// ---------- references ----------
function allRefs(){
  const out = [];
  P.ref_groups.forEach(g => g.refs.forEach(r => out.push(r)));
  return out;
}
function nextRefId(){
  let mx = 0;
  allRefs().forEach(r => { const m = /^cit(\d+)$/.exec(r.id || ''); if (m) mx = Math.max(mx, +m[1]); });
  return 'cit' + String(mx + 1).padStart(3, '0');
}
function refPlain(r){ const d = document.createElement('div'); d.innerHTML = r.html; return d.textContent.trim(); }

function renderRefs(){
  const c = $('#refgroups'); c.innerHTML = '';
  P.ref_groups.forEach((g, gi) => {
    const card = document.createElement('div'); card.className = 'card';
    card.innerHTML = `<label>List title</label><input type="text" value="${escAttr(g.title)}">
      <div class="refs" style="margin-top:10px"></div>
      <button class="small ghost">+ add reference</button>
      <button class="small danger" style="float:right">delete list</button>`;
    card.querySelector('input').addEventListener('input', e => { g.title = e.target.value; markDirty(); });
    const refsDiv = card.querySelector('.refs');
    g.refs.forEach((r, ri) => {
      const row = document.createElement('div'); row.className = 'refrow';
      row.innerHTML = `<div class="rid">${r.id}${refHasDoi(r) ? ' <span class="hasdoi" title="this entry already carries a DOI">DOI</span>' : ''}</div><div class="ed" contenteditable="true"></div>
        <div class="bbtns"><button>&uarr;</button><button>&darr;</button><button>&#10005;</button></div>`;
      const ed = row.querySelector('.ed');
      ed.innerHTML = r.html || '';
      ed.addEventListener('input', () => { r.html = ed.innerHTML; delete doiSug[r.id]; markDirty(); });
      const [up, down, del] = row.querySelectorAll('.bbtns button');
      up.onclick = () => { if (ri>0){ [g.refs[ri-1], g.refs[ri]] = [g.refs[ri], g.refs[ri-1]]; markDirty(); renderRefs(); } };
      down.onclick = () => { if (ri<g.refs.length-1){ [g.refs[ri+1], g.refs[ri]] = [g.refs[ri], g.refs[ri+1]]; markDirty(); renderRefs(); } };
      del.onclick = () => { if (confirm('Delete this reference? In-text citations pointing to it will unlink.')){ g.refs.splice(ri,1); markDirty(); renderRefs(); } };
      refsDiv.appendChild(row);
      const box = doiBox(r);
      if (box) refsDiv.appendChild(box);
    });
    card.querySelector('button.ghost').onclick = () => { g.refs.push({id: nextRefId(), html: ''}); markDirty(); renderRefs(); };
    card.querySelector('button.danger').onclick = () => {
      if (confirm('Delete this whole reference list?')) { P.ref_groups.splice(gi,1); markDirty(); renderRefs(); }
    };
    c.appendChild(card);
  });
  const btn = document.createElement('button'); btn.className = 'ghost'; btn.textContent = '+ Add a reference list (e.g. Works Cited)';
  btn.onclick = () => { P.ref_groups.push({title: 'Works Cited', refs: []}); markDirty(); renderRefs(); };
  c.appendChild(btn);
}

// ---------- crossref DOI lookup ----------
const DOI_IN_TEXT = /(?:doi:\s*|https?:\/\/(?:dx\.)?doi\.org\/)10\./i;
let doiSug = {};        // ref id -> what Crossref came back with
let doiBusy = false;

function refHasDoi(r){ return DOI_IN_TEXT.test(refPlain(r)); }
function doiStatus(msg){ const el = $('#doistatus'); if (el) el.textContent = msg; }
function refById(rid){ return allRefs().find(r => r.id === rid); }

function doiBox(r){
  const s = doiSug[r.id];
  if (!s) return null;
  const box = document.createElement('div');
  if (s.status === 'none' || s.status === 'error') {
    box.className = 'doibox weak';
    box.innerHTML = s.status === 'error'
      ? `<span class="dwhy">Crossref lookup failed: ${escAttr(s.message||'')}</span>`
      : `<span class="dwhy">No DOI found on Crossref for this entry.</span>`;
    return box;
  }
  box.className = 'doibox' + (s.status === 'weak' ? ' weak' : '');
  box.innerHTML = `
    <div class="dtitle">${escAttr(s.title||'')}</div>
    <div class="dmeta">${escAttr(s.authors||'')}${s.authors && s.container ? ' &middot; ' : ''}${escAttr(s.container||'')}${s.year ? ' &middot; ' + s.year : ''}${s.type ? ' &middot; ' + escAttr(s.type) : ''}</div>
    <div class="dmeta"><code>https://doi.org/${escAttr(s.doi)}</code>
      <a href="https://doi.org/${escAttr(s.doi)}" target="_blank" rel="noopener">open</a></div>
    <button data-a="yes">Use this DOI</button><button class="no" data-a="no">Not this one</button>
    <span class="dwhy">${s.status === 'weak' ? '&#9888; not confident &mdash; ' : ''}${escAttr(s.why||'')}</span>`;
  box.addEventListener('click', e => {
    const a = e.target.dataset && e.target.dataset.a;
    if (a === 'yes') acceptDoi(r.id);
    if (a === 'no') rejectDoi(r.id);
  });
  return box;
}

function acceptDoi(rid){
  const r = refById(rid), s = doiSug[rid];
  if (!r || !s || !s.doi) return;
  let h = (r.html || '').replace(/\s+$/, '');
  if (!/[.!?][)\]"'”’]?$/.test(refPlain({html: h}))) h += '.';
  r.html = h + ' https://doi.org/' + s.doi + '.';
  delete doiSug[rid];
  markDirty(); renderRefs();
}
function rejectDoi(rid){
  const r = refById(rid);
  if (r) r.no_doi = true;      // don't offer this one again
  delete doiSug[rid];
  markDirty(); renderRefs();
}
function acceptAllStrong(){
  const ids = Object.keys(doiSug).filter(k => doiSug[k].status === 'strong');
  if (!ids.length) { doiStatus('No confident matches waiting.'); return; }
  ids.forEach(acceptDoi);
  doiStatus('Added ' + ids.length + ' DOI' + (ids.length === 1 ? '' : 's') + '.');
}

async function findDois(){
  if (doiBusy) return;
  const todo = allRefs().filter(r => !refHasDoi(r) && !r.no_doi && refPlain(r).length > 12);
  if (!todo.length) { doiStatus('Nothing to look up — every entry has a DOI or was passed over.'); return; }
  doiBusy = true;
  let done = 0, found = 0;
  doiStatus('checking ' + todo.length + ' entries on Crossref…');
  for (let i = 0; i < todo.length; i += 4) {
    const ids = todo.slice(i, i + 4).map(r => r.id);
    let j;
    try {
      const resp = await fetch('/crossref/' + P.id, {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ref_groups: P.ref_groups, ids})});
      j = await resp.json();
    } catch (e) { doiStatus('Crossref lookup failed — is this machine online?'); break; }
    if (!j.ok) { doiStatus('Crossref lookup failed: ' + (j.error || '')); break; }
    (j.results || []).forEach(res => {
      doiSug[res.id] = res;
      if (res.status === 'strong' || res.status === 'weak') found++;
    });
    done += ids.length;
    renderRefs();
    doiStatus('checked ' + done + ' of ' + todo.length + ' — ' + found + ' possible DOI' + (found === 1 ? '' : 's'));
  }
  doiBusy = false;
  renderRefs();
  if (done >= todo.length) {
    doiStatus('Done: ' + found + ' of ' + todo.length + ' entries got a suggestion. Accept or dismiss each one.');
  }
}

// ---------- crossref DOI lookup, notes ----------
// Most BC Studies articles cite in footnotes, so the full citations sit
// inside the notes, several to a note. The server finds the ones that look
// like a first, full citation (a title and a year) and asks Crossref; each
// hit says where its DOI goes ("at", a plain-text offset in the paragraph).
let noteSug = new Map();    // note part -> [hit, ...]
let noteDoiBusy = false;
function noteDoiStatus(msg){ const el = $('#notedoistatus'); if (el) el.textContent = msg; }

// Put plain text into editor HTML at plain-text character `at`, replacing
// the `drop` characters there, counting the way the server does (an entity
// is one character, <br> one). Tags are kept; a link left empty goes.
function insertAtPlain(html, at, text, drop){
  const safe = text.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const end = at + (drop || 0);
  let out = '', count = 0, done = false;
  for (const chunk of (html || '').split(/(<[^>]*>)/)) {
    if (!chunk) continue;
    if (chunk[0] === '<') {
      if (/^<br\b/i.test(chunk)) {
        if (!done && count === at) { out += safe; done = true; }
        if (count >= at && count < end) { count++; continue; }
        count++;
      }
      out += chunk; continue;
    }
    for (const piece of chunk.split(/(&#?\w+;)/)) {
      if (!piece) continue;
      const ent = piece[0] === '&' && piece.endsWith(';');
      const chars = ent ? [piece] : [...piece];
      for (const ch of chars) {
        if (!done && count === at) { out += safe; done = true; }
        if (!(count >= at && count < end)) out += ch;
        count++;
      }
    }
  }
  if (!done) out += safe;
  out = out.replace(/<a\b[^>]*><\/a>/gi, '');
  // a link whose words were swapped for a DOI now goes to the DOI
  if (drop) out = out.replace(/<a\b[^>]*>(https:\/\/doi\.org\/[^<]+)<\/a>/gi,
                              (m, u) => '<a href="' + u.replace(/"/g, '&quot;') + '">' + u + '</a>');
  return out;
}

function noteDoiBoxes(part){
  const hits = (noteSug.get(part) || []).filter(s => !(part.no_doi || []).includes(s.doi));
  return hits.map(s => {
    const box = document.createElement('div');
    const cite = `<div class="dmeta">In the note: &ldquo;${escAttr(s.cite.length > 110 ? s.cite.slice(0, 110) + '…' : s.cite)}&rdquo;</div>`;
    if (s.status === 'none' || s.status === 'error') {
      box.className = 'doibox weak';
      box.innerHTML = cite + (s.status === 'error'
        ? `<span class="dwhy">Crossref lookup failed: ${escAttr(s.message||'')}</span>`
        : `<span class="dwhy">No DOI found on Crossref for this citation.</span>`);
      return box;
    }
    box.className = 'doibox' + (s.status === 'weak' ? ' weak' : '');
    box.innerHTML = cite + `
      <div class="dtitle">${escAttr(s.title||'')}</div>
      <div class="dmeta">${escAttr(s.authors||'')}${s.authors && s.container ? ' &middot; ' : ''}${escAttr(s.container||'')}${s.year ? ' &middot; ' + s.year : ''}${s.type ? ' &middot; ' + escAttr(s.type) : ''}</div>
      <div class="dmeta"><code>https://doi.org/${escAttr(s.doi)}</code>
        <a href="https://doi.org/${escAttr(s.doi)}" target="_blank" rel="noopener">open</a></div>
      <button data-a="yes">Use this DOI</button><button class="no" data-a="no">Not this one</button>
      <span class="dwhy">${s.status === 'weak' ? '&#9888; not confident &mdash; ' : ''}${escAttr(s.why||'')}</span>
      ${s.replaces ? `<div class="dwhy">Replaces the link <code>${escAttr(s.replaces)}</code> &mdash; Chicago cites the DOI instead of a URL.</div>` : ''}`;
    box.addEventListener('click', e => {
      const a = e.target.dataset && e.target.dataset.a;
      if (a === 'yes') { acceptNoteDoi(part, s); renderNotes(); }
      if (a === 'no') { rejectNoteDoi(part, s); renderNotes(); }
    });
    return box;
  });
}

function dropNoteHit(part, s){
  const left = (noteSug.get(part) || []).filter(x => x !== s);
  if (left.length) noteSug.set(part, left); else noteSug.delete(part);
}
function acceptNoteDoi(part, s){
  const doi = 'https://doi.org/' + s.doi;
  const add = s.drop ? doi : ', ' + doi;      // in place of a URL, or after the citation
  part.html = insertAtPlain(part.html, s.at, add, s.drop);
  // the other citations after this one in the same paragraph move along
  (noteSug.get(part) || []).forEach(x => { if (x !== s && x.at >= s.at) x.at += add.length - (s.drop || 0); });
  dropNoteHit(part, s);
  markDirty();
}
function rejectNoteDoi(part, s){
  part.no_doi = (part.no_doi || []).concat([s.doi]);   // don't offer this one again
  dropNoteHit(part, s);
  markDirty();
}
function acceptAllStrongNotes(){
  let n = 0;
  noteSug.forEach((hits, part) => {
    // right to left, so each insert leaves the earlier offsets where they were
    hits.filter(s => s.status === 'strong' && !(part.no_doi || []).includes(s.doi))
        .sort((a, b) => b.at - a.at)
        .forEach(s => { acceptNoteDoi(part, s); n++; });
  });
  renderNotes();
  noteDoiStatus(n ? 'Added ' + n + ' DOI' + (n === 1 ? '' : 's') + '.' : 'No confident matches waiting.');
}

async function findNoteDois(){
  if (noteDoiBusy) return;
  const todo = [];
  P.notes.forEach((n, ni) => n.parts.forEach((p, pi) => {
    if (/\b(1[5-9]\d\d|20\d\d)\b/.test(refPlain(p))) todo.push([ni, pi]);
  }));
  if (!todo.length) { noteDoiStatus('No notes with a dated citation to look up.'); return; }
  noteDoiBusy = true; noteSug = new Map();
  let done = 0, found = 0;
  noteDoiStatus('checking ' + todo.length + ' note paragraphs on Crossref…');
  for (let i = 0; i < todo.length; i += 3) {
    const batch = todo.slice(i, i + 3);
    let j;
    try {
      const resp = await fetch('/crossref_notes/' + P.id, {method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({notes: P.notes, parts: batch})});
      j = await resp.json();
    } catch (e) { noteDoiStatus('Crossref lookup failed — is this machine online?'); break; }
    if (!j.ok) { noteDoiStatus('Crossref lookup failed: ' + (j.error || '')); break; }
    (j.results || []).forEach(res => {
      const part = (P.notes[res.note] || {parts: []}).parts[res.part];
      // skip a paragraph edited while its lookup was out: the offsets are stale
      if (!part || part.html !== res.html) return;
      const hits = res.hits.filter(h => h.status !== 'none');   // a note full of "no DOI" boxes is noise
      if (hits.length) noteSug.set(part, hits);
      found += res.hits.filter(h => h.status === 'strong' || h.status === 'weak').length;
    });
    done += batch.length;
    renderNotes();
    noteDoiStatus('checked ' + done + ' of ' + todo.length + ' note paragraphs — ' + found + ' possible DOI' + (found === 1 ? '' : 's'));
  }
  noteDoiBusy = false;
  renderNotes();
  if (done >= todo.length) {
    noteDoiStatus('Done: ' + found + ' possible DOI' + (found === 1 ? '' : 's') + ' found in the notes. Accept or dismiss each one.');
  }
}

// ---------- citations review ----------
function citableHolders(){
  const out = [];
  P.blocks.forEach(b => { if (['p','blockquote','epigraph'].includes(b.kind)) out.push(b); });
  P.notes.forEach(n => n.parts.forEach(p => out.push(p)));
  return out;
}
function renderCitations(){
  const c = $('#citlist'); c.innerHTML = '';
  if (citeReturn && citeReturn.holder) {
    const back = document.createElement('div');
    back.className = 'citreturn';
    back.innerHTML = '<button type="button" class="small">&#8617; Back to the text</button> '
      + '<span class="hint">returns you to the citation you opened this tab from</span>';
    const from = citeReturn;
    back.querySelector('button').onclick = () => jumpToText(from.holder, from.k);
    c.appendChild(back);
  }
  const refs = allRefs();
  const refOpts = refs.map(r => `<option value="${r.id}">${escAttr(refPlain(r).slice(0, 80))}</option>`).join('');
  let total = 0, needs = 0;
  citableHolders().forEach(holder => {
    const dom = document.createElement('div');
    dom.innerHTML = holder.html || '';
    dom.querySelectorAll('cite').forEach((el, k) => {
      total++;
      const rid = el.dataset.rid || '', status = el.dataset.status || 'none', basis = el.dataset.basis || '';
      if (status !== 'confirmed') needs++;
      const before = (el.previousSibling && el.parentNode.textContent) ? contextBefore(el) : '';
      const after = contextAfter(el);
      const row = document.createElement('div'); row.className = 'citrow';
      row.dataset.cidx = String(total - 1);
      const basisNote = {name:'matched by author name', context:'guessed from context — check!', title:'matched by title',
                         manual:'marked by hand', ambiguous:'surname matches several entries', unmatched:'no match found', '':''}[basis] || '';
      row.innerHTML = `
        <div class="ctx">…${escapeHtml(before)}<b>${escapeHtml(el.textContent)}</b>${escapeHtml(after)}…<br>
          <span class="citation-basis">${basisNote}</span></div>
        <div><select><option value="">— not linked —</option>${refOpts}</select></div>
        <div><span class="badge b-${status}">${status === 'auto' ? 'guessed' : status === 'confirmed' ? 'confirmed' : 'not linked'}</span><br>
          <button class="small" style="margin-top:4px">&#10003; confirm</button>
          <button class="small ghost" style="margin-top:4px" title="not a citation">&#10005;</button>
          <button type="button" class="small ghost cit-go-text" style="margin-top:4px" title="jump to this citation in the text">&#8617; show in text</button></div>`;
      const sel = row.querySelector('select');
      sel.value = rid;
      sel.addEventListener('change', () => updateCite(holder, k, cite => {
        cite.dataset.rid = sel.value;
        cite.dataset.status = sel.value ? 'confirmed' : 'none';
        cite.dataset.basis = 'manual';
      }));
      const [confirmBtn, removeBtn] = row.querySelectorAll('div:last-child button');
      confirmBtn.onclick = () => updateCite(holder, k, cite => {
        if (!cite.dataset.rid) { alert('Pick a Works Cited entry first.'); throw new Error('no rid'); }
        cite.dataset.status = 'confirmed';
      });
      removeBtn.onclick = () => updateCite(holder, k, cite => {
        cite.replaceWith(...cite.childNodes);   // unwrap: it was not a citation
      });
      row.querySelector('.cit-go-text').onclick = () => jumpToText(holder, k);
      c.appendChild(row);
    });
  });
  $('#citsummary').textContent = total
    ? `${total} citation(s) found — ${needs} still to confirm. Yellow = guessed, green = confirmed, red = not linked.`
    : 'No in-text citations marked yet. Use “Re-scan” (after adding references) or select text in the Body tab and click “Mark as citation”.';
}
function updateCite(holder, k, fn){
  const dom = document.createElement('div');
  dom.innerHTML = holder.html || '';
  const cites = dom.querySelectorAll('cite');
  if (!cites[k]) return;
  try { fn(cites[k]); } catch (e) { return; }
  holder.html = dom.innerHTML;
  markDirty(); renderBlocks(); renderNotes(); renderCitations();
}
function contextBefore(el){
  let t = '', n = el;
  while (t.length < 60) {
    n = prevTextish(n);
    if (!n) break;
    t = n.textContent + t;
  }
  return t.slice(-60);
}
function contextAfter(el){
  let t = '', n = el;
  while (t.length < 60) {
    n = nextTextish(n);
    if (!n) break;
    t += n.textContent;
  }
  return t.slice(0, 60);
}
function prevTextish(n){ while (n && !n.previousSibling) n = n.parentNode; return n && n.previousSibling; }
function nextTextish(n){ while (n && !n.nextSibling) n = n.parentNode; return n && n.nextSibling; }
function escapeHtml(s){ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function confirmAllGuesses(){
  citableHolders().forEach(holder => {
    const dom = document.createElement('div');
    dom.innerHTML = holder.html || '';
    let changed = false;
    dom.querySelectorAll('cite[data-status="auto"]').forEach(el => { if (el.dataset.rid) { el.dataset.status = 'confirmed'; changed = true; } });
    if (changed) holder.html = dom.innerHTML;
  });
  markDirty(); renderBlocks(); renderNotes(); renderCitations();
}
async function rescan(){
  const r = await fetch('/rescan/' + P.id, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(P)});
  const data = await r.json();
  if (data.ok) {
    Object.assign(P, data.project);
    dirty = false; $('#savestatus').textContent = 'saved';
    renderBlocks(); renderNotes(); renderRefs(); renderCitations();
  }
}

// ---------- preview ----------
function audioPreview(b){
  const f = (b.file || '').trim();
  return `<div id="${escAttr(b.id || '')}" style="margin:14px 0;padding:6px 0 6px 14px;border-left:4px solid #0b1e34">`
    + (b.label ? `<div style="font-weight:700">${escapeHtml(b.label)}</div>` : '')
    + (b.caption_title ? `<div style="font-weight:600">${escapeHtml(b.caption_title)}</div>` : '')
    + (b.html ? `<div style="font-size:.9rem;color:#444">${b.html}</div>` : '')
    + (f && mediaFiles && mediaFiles.has(f)
         ? `<audio controls preload="none" style="width:100%;margin-top:4px" src="${escAttr(mediaUrl(f))}"></audio>`
         : `<div style="color:#888;font-size:.85rem">[ audio: ${escapeHtml(f || '(no file)')} ]</div>`)
    + `</div>`;
}

function renderPreview(){
  const c = $('#previewbody');
  ensureFigIds();
  ensureAudIds();
  let h = `<h2 class="t">${titleHtml(P.meta.title) || '(untitled)'}</h2><div class="by">${escapeHtml(P.meta.authors || '')}</div>`;
  // the galley prints the players at the top, above the abstract, wherever
  // the blocks sit in the body
  h += audioBlocks().map(audioPreview).join('');
  P.blocks.forEach(b => {
    const inner = b.html || '';
    if (b.kind === 'heading') h += `<h${(b.level||1)+2}>${inner}</h${(b.level||1)+2}>`;
    else if (b.kind === 'blockquote' || b.kind === 'epigraph') h += `<blockquote>${inner}</blockquote>`;
    else if (b.kind === 'epigraph-source') h += `<blockquote class="hint">${inner}</blockquote>`;
    else if (b.kind === 'verse') h += `<div class="verse">${inner}</div>`;
    else if (b.kind === 'verse-break') h += `<div style="height:1em"></div>`;
    else if (b.kind === 'divider') h += `<p style="text-align:center">•</p>`;
    else if (b.kind === 'figure') {
      const fn = escapeHtml(b.file || '(no image file)');
      h += `<figure id="${escAttr(b.id || '')}" style="margin:14px 0;padding:10px;border:1px dashed #bbb;background:#fafafa;text-align:center">`
         + (hasMedia(b)
              ? `<img src="${escAttr(mediaUrl(b.file))}" alt="${escAttr(b.alt || '')}" style="max-width:100%;height:auto">`
              : `<div style="color:#888;font-size:.85rem">[ image: ${fn} ]</div>`)
         + (b.label ? `<div style="font-weight:700;margin-top:4px">${escapeHtml(b.label)}</div>` : '')
         + (inner ? `<figcaption style="font-size:.9rem;color:#444;margin-top:2px">${inner}</figcaption>` : '')
         + `</figure>`;
    }
    else if (b.kind === 'audio') { /* printed at the top -- see audioPreview() */ }
    else if (b.kind === 'table') {
      const hr = +b.header_rows || 0;
      h += `<div id="${escAttr(b.id || '')}" class="prevtable">`
         + (b.label ? `<div style="font-weight:700">${escapeHtml(b.label)}</div>` : '')
         + (inner ? `<div class="hint" style="color:#333">${inner}</div>` : '')
         + '<table>' + (b.rows || []).map((row, r) => '<tr>' + row.map(c => {
             const tag = r < hr || c.th ? 'th' : 'td';
             return `<${tag} colspan="${+c.colspan || 1}" rowspan="${+c.rowspan || 1}">${c.html || ''}</${tag}>`;
           }).join('') + '</tr>').join('') + '</table>'
         + (b.foot_html ? `<div class="hint" style="font-size:.85rem">${b.foot_html}</div>` : '')
         + '</div>';
    }
    else h += `<p>${inner}</p>`;
  });
  if (P.notes.length) {
    h += '<h3>Notes</h3><ol>' + P.notes.map(n => '<li>' + n.parts.map(p => `<p>${p.html}</p>`).join('') + '</li>').join('') + '</ol>';
  }
  P.ref_groups.forEach(g => {
    if (g.refs.length) h += `<h3>${escapeHtml(g.title)}</h3>` + g.refs.map(r => `<p style="padding-left:2em;text-indent:-2em">${r.html}</p>`).join('');
  });
  c.innerHTML = h;
  // make figure references jump to the figure, the way the galley will
  c.querySelectorAll('a.figref[data-fig]').forEach(a => {
    a.style.cursor = 'pointer';
    a.onclick = () => { const t = c.querySelector('#' + CSS.escape(a.dataset.fig)); if (t) t.scrollIntoView({block:'center'}); };
  });
}

// ---------- save & generate ----------
async function saveNow(){
  $('#savestatus').textContent = 'saving…';
  try {
    const r = await fetch('/save/' + P.id, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(P)});
    if ((await r.json()).ok) { dirty = false; $('#savestatus').textContent = 'saved'; }
  } catch (e) { $('#savestatus').textContent = 'save failed — is the server running?'; }
}
async function generate(){
  $('#genresult').innerHTML = '<p>Generating…</p>';
  const r = await fetch('/generate/' + P.id, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(P)});
  const data = await r.json();
  if (!data.ok) { $('#genresult').innerHTML = `<p class="error">${escapeHtml(data.error || 'Failed')}</p>`; return; }
  dirty = false; $('#savestatus').textContent = 'saved';
  const v = data.validation;
  const vklass = 'v-' + v.status;
  const vlabel = {valid: '✓ Valid JATS 1.4 (checked against the DTD)', invalid: '✗ XML has validation problems',
                  skipped: '– Validation skipped'}[v.status];
  let h = `<div class="genout"><p class="${vklass}">${vlabel}</p>`;
  if (v.messages.length) h += '<ul>' + v.messages.map(m => `<li class="hint">${escapeHtml(m)}</li>`).join('') + '</ul>';
  if (data.warnings.length) h += '<p><b>Things to check:</b></p><ul>' + data.warnings.map(w => `<li class="hint">${escapeHtml(w)}</li>`).join('') + '</ul>';
  const s = data.stats;
  h += `<p class="hint">${s.sections} section(s) · ${s.refs} reference(s) · ${s.linked_citations} linked citation(s)`
     + (s.unlinked_citations ? ` · <b>${s.unlinked_citations} citation(s) not linked</b>` : '')
     + ` · ${s.notes} note(s) · ${s.ext_links} clickable link(s)`
     + (s.figures ? ` · ${s.figures} figure(s) with ${s.fig_links} in-text figure link(s)` : '')
     + (s.audio ? ` · ${s.audio} audio clip(s)` : '')
     + `</p>`;
  const iss = escapeHtml(data.issue_folder || 'UNKNOWN');
  h += `<p><a class="btn" href="/download_all/${P.id}">Download files</a></p>`;
  h += `<p class="hint">One zip holding <code>${iss}/HTML</code> (the galley, <code>style.css</code>, `
     + `<code>logo.png</code> and any images or audio) and <code>${iss}/Archival-XML</code>. Unzip it where `
     + `you keep the rest of the issue and every article goes in the same <code>${iss}</code> folder.</p>`;
  h += `<p class="hint"><b>For OJS:</b> upload the <code>.html</code> file from <code>${iss}/HTML</code> as the `
     + `HTML galley, then add <code>style.css</code>, <code>logo.png</code> and each image or audio file `
     + `as <b>dependent files</b>, each named exactly as it is in the folder. Nothing from `
     + `<code>Archival-XML</code> goes on OJS.</p>`;
  h += `<p class="hint">Or download one file: `
     + `<a href="/download_html/${P.id}">HTML galley</a> &middot; `
     + `<a href="/download/${P.id}/archival">archival XML</a></p>`;
  if (data.archive_ok) {
    h += `<p class="hint">The archival XML is the preservation copy. It was also saved to `
       + `<code>${escapeHtml(data.archive_path)}</code> — that folder isn't changed when you delete drafts, `
       + `so back it up.</p>`;
  }
  h += `</div>`;
  $('#genresult').innerHTML = h;
}

// ---------- in-text citation hover card ----------
// hover any <cite> in the Body/Notes/Preview tabs and see which reference-list
// entry it points at without leaving the text.
let tipEl = null, tipHideT = null;
const BASIS_NOTE = {
  name: 'matched by author name', context: 'guessed from context — check',
  title: 'matched by title', manual: 'linked by hand',
  ambiguous: 'surname matches several entries', unmatched: 'no matching entry found',
};

function citeTipEl(){
  if (!tipEl) {
    tipEl = document.createElement('div');
    tipEl.className = 'citetip';
    tipEl.addEventListener('mouseenter', () => clearTimeout(tipHideT));
    tipEl.addEventListener('mouseleave', hideCiteTip);
    document.body.appendChild(tipEl);
  }
  return tipEl;
}
function hideCiteTip(){
  clearTimeout(tipHideT);
  tipHideT = setTimeout(() => { if (tipEl) tipEl.style.display = 'none'; }, 200);
}
function hideCiteTipNow(){ clearTimeout(tipHideT); if (tipEl) tipEl.style.display = 'none'; }

// which block this cite sits in, its spot inside that block, and its spot
// among ALL the draft's cites (that last one is the Citations-tab row number)
function citeLocation(el){
  const ed = el.closest('.ed');
  if (!ed || !ed.__holder) return null;
  const holders = citableHolders();
  const hi = holders.indexOf(ed.__holder);
  if (hi < 0) return null;
  const k = [...ed.querySelectorAll('cite')].indexOf(el);
  if (k < 0) return null;
  let n = 0;
  for (let i = 0; i < hi; i++) {
    const d = document.createElement('div');
    d.innerHTML = holders[i].html || '';
    n += d.querySelectorAll('cite').length;
  }
  return { holder: ed.__holder, k: k, gidx: n + k };
}

// after a re-render the old <cite> node is gone; find the new one
function findCiteEl(holder, k){
  const ed = [...document.querySelectorAll('.ed')].find(e => e.__holder === holder);
  return ed ? (ed.querySelectorAll('cite')[k] || null) : null;
}

// confirm a guessed link straight from the hover card
function confirmFromTip(loc){
  updateCite(loc.holder, loc.k, c => { c.dataset.status = 'confirmed'; });
  const fresh = findCiteEl(loc.holder, loc.k);
  if (fresh) showCiteTip(fresh); else hideCiteTipNow();
}

function showCiteTip(el){
  clearTimeout(tipHideT);
  const t = citeTipEl();
  const rid = el.dataset.rid || '', status = el.dataset.status || 'none';
  const ref = allRefs().find(r => r.id === rid);
  const label = status === 'confirmed' ? '✓ confirmed link'
              : status === 'auto' ? 'guessed — not confirmed yet'
              : 'not linked';
  let h = `<div class="ct-head"><span class="badge b-${status}">${escapeHtml(label)}</span></div>`;
  if (ref) {
    h += `<div class="ct-ref">${ref.html || escapeHtml(rid)}</div>`;
    if (refHasDoi(ref)) h += `<div class="ct-doi">this entry carries a DOI</div>`;
  } else if (rid) {
    h += `<div class="ct-ref none">Points at ${escapeHtml(rid)}, which is no longer in the reference list.</div>`;
  } else {
    h += `<div class="ct-ref none">No reference-list entry chosen yet — pick one in the Citations tab.</div>`;
  }
  const basis = BASIS_NOTE[el.dataset.basis || ''] || '';
  if (basis) h += `<div class="ct-basis">${escapeHtml(basis)}</div>`;
  const loc = citeLocation(el);
  if (loc) {
    h += `<div class="ct-btns">`;
    if (status === 'auto' && ref) h += `<button class="small ct-ok">&#10003; Confirm this link</button>`;
    h += `<button class="small ghost ct-go">Review in Citations tab →</button></div>`;
  }
  t.innerHTML = h;
  const ok = t.querySelector('.ct-ok');
  if (ok) ok.onclick = () => confirmFromTip(loc);
  const go = t.querySelector('.ct-go');
  if (go) go.onclick = () => { hideCiteTipNow(); jumpToCitation(loc.gidx, loc); };
  t.style.display = 'block';
  t.style.left = '0px'; t.style.top = '0px';          // measure first
  const r = el.getBoundingClientRect();
  const w = t.offsetWidth, ht = t.offsetHeight;
  t.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.left)) + 'px';
  const fitsBelow = r.bottom + 8 + ht < window.innerHeight - 8;
  t.style.top = (fitsBelow || r.top < ht + 16 ? r.bottom + 8 : r.top - ht - 8) + 'px';
}

function jumpToCitation(idx, from){
  citeReturn = from ? { holder: from.holder, k: from.k } : null;
  showTab('citations');
  const row = document.querySelector('.citrow[data-cidx="' + idx + '"]');
  if (!row) return;
  row.scrollIntoView({ block: 'center', behavior: 'smooth' });
  row.classList.add('flash');
  setTimeout(() => row.classList.remove('flash'), 1600);
}

function wireCiteTips(){
  document.addEventListener('mouseover', e => {
    if (!e.target.closest) return;
    const c = e.target.closest('cite');
    if (c && (c.closest('.ed') || c.closest('#previewbody'))) showCiteTip(c);
  });
  document.addEventListener('mouseout', e => {
    if (e.target.closest && e.target.closest('cite')) hideCiteTip();
  });
  window.addEventListener('scroll', hideCiteTipNow, true);
}

// ---------- contributor bios: one box per contributor ----------
// Each box is {name, html}. The name is matched to the Author(s) byline the
// same way bcs_jats_render._assign_bio_boxes does it, so the tick beside a
// name is exactly what the XML will do. Older drafts only have bios_html;
// their boxes are built from it on first open and nothing is written back
// until a box is edited, so an untouched draft renders exactly as before.
let bioBoxes = null;
const BIO_NAME_SUFFIXES = ['jr', 'sr', 'ii', 'iii', 'iv', 'v'];

// JS twin of bcs_names.split_byline -> [[surname, given], ...]
function splitByline(byline){
  let text = String(byline || '').split(/\s+/).filter(Boolean).join(' ');
  text = text.replace(/[*\u2020\u2021]+/g, '');
  text = text.replace(/\s*\([^)]*\)/g, '');
  const people = [];
  text.split(/,\s*and\s+|\s+and\s+|\s*&\s*|,\s*/).forEach(part => {
    part = (part || '').trim();
    if (!part) return;
    if (people.length && BIO_NAME_SUFFIXES.includes(part.replace(/\.+$/, '').toLowerCase())) {
      const last = people[people.length - 1];
      last[1] = (last[1] + ' ' + part).trim();
      return;
    }
    const bits = part.split(/\s+/);
    if (bits.length >= 2) people.push([bits[bits.length - 1], bits.slice(0, -1).join(' ')]);
    else people.push([bits[0], '']);
  });
  return people;
}
// twin of bcs_jats_render._name_key: no accents, no punctuation, lower case
function nameKey(s){
  return String(s || '').normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
    .replace(/[^\p{L}\p{N}_\s]/gu, ' ').split(/\s+/).filter(Boolean).join(' ');
}
// twin of bcs_jats_render._match_bio_name: full name first, then surname
function matchBioName(name, people){
  const key = nameKey(name);
  if (!key) return -1;
  let hits = [];
  people.forEach(([s, g], i) => { const f = nameKey(g + ' ' + s); if (f && f === key) hits.push(i); });
  if (hits.length === 1) return hits[0];
  const padded = ' ' + key + ' ';
  hits = [];
  people.forEach(([s], i) => { const sk = nameKey(s); if (sk && padded.includes(' ' + sk + ' ')) hits.push(i); });
  return hits.length === 1 ? hits[0] : -1;
}
function bioPlain(h){
  const d = document.createElement('div');
  d.innerHTML = h || '';
  return (d.textContent || '').replace(/\u00a0/g, ' ').trim();
}
// the name a Contributors paragraph opens with, in small caps or bold
function bioLeadName(h){
  const d = document.createElement('div');
  d.innerHTML = h || '';
  const first = d.querySelector('.sc, b, strong');
  if (!first) return '';
  const t = (first.textContent || '').trim();
  return t && (d.textContent || '').trim().startsWith(t) ? t.replace(/[\s,.:;]+$/, '') : '';
}
function asBioPara(h){ return /^\s*<(p|div)[\s>]/i.test(h || '') ? h : '<p>' + (h || '') + '</p>'; }

function initialBioBoxes(){
  if (Array.isArray(P.meta.bios)) {
    return P.meta.bios.map(b => ({ name: String((b && b.name) || ''), html: String((b && b.html) || '') }));
  }
  const people = splitByline(P.meta.authors || '');
  const d = document.createElement('div');
  d.innerHTML = P.meta.bios_html || '';
  const loose = [...d.childNodes].some(n =>
    !(n.nodeType === 1 && /^(P|DIV)$/.test(n.tagName)) && (n.textContent || '').trim());
  let paras = loose ? [d.innerHTML.trim()]
    : [...d.children].map(x => x.innerHTML.trim()).filter(h => bioPlain(h));
  if (!people.length) {
    return paras.length ? paras.map(h => ({ name: bioLeadName(h), html: '<p>' + h + '</p>' }))
                        : [{ name: '', html: '' }];
  }
  const boxes = people.map(([s, g]) => ({ name: (g + ' ' + s).trim(), html: '' }));
  const extra = [];
  paras.forEach(h => {
    let who = -1;
    if (people.length === 1) who = 0;
    else {
      const lead = bioLeadName(h);
      if (lead) who = matchBioName(lead, people);
      if (who < 0) {
        const plain = bioPlain(h).toLowerCase();
        const hits = [];
        people.forEach(([s], i) => { if (s && plain.includes(s.toLowerCase())) hits.push(i); });
        if (hits.length === 1) who = hits[0];
      }
    }
    if (who >= 0) boxes[who].html += '<p>' + h + '</p>';
    else extra.push({ name: bioLeadName(h), html: '<p>' + h + '</p>' });
  });
  return boxes.concat(extra);
}

function commitBios(){
  P.meta.bios = bioBoxes.map(b => ({ name: b.name, html: b.html }));
  // the single field is kept in step so older code paths still see every bio
  P.meta.bios_html = bioBoxes.filter(b => bioPlain(b.html)).map(b => asBioPara(b.html)).join('');
  markDirty();
}
function fillBioDatalist(){
  const dl = document.getElementById('bio-author-names');
  if (!dl) return;
  dl.innerHTML = '';
  splitByline(P.meta.authors || '').forEach(([s, g]) => {
    const o = document.createElement('option');
    o.value = (g + ' ' + s).trim();
    dl.appendChild(o);
  });
}
function renderBios(){
  const c = $('#biolist');
  if (!c) return;
  if (!bioBoxes) bioBoxes = initialBioBoxes();
  c.innerHTML = '';
  const dl = document.createElement('datalist');
  dl.id = 'bio-author-names';
  c.appendChild(dl);
  fillBioDatalist();
  bioBoxes.forEach((box, i) => {
    const card = document.createElement('div');
    card.className = 'biobox';
    card.innerHTML = `<div class="biohead"><label>Contributor ${i + 1}</label>
      <input type="text" list="bio-author-names" placeholder="Name as it appears in the Author(s) field">
      <span class="biomatch"></span>
      <button type="button" class="small ghost" title="move up">&uarr;</button>
      <button type="button" class="small ghost" title="move down">&darr;</button>
      <button type="button" class="small danger" title="remove this contributor">remove</button></div>
      <div class="ed" contenteditable="true" data-ph="Paste this contributor's bio here"></div>`;
    const inp = card.querySelector('input');
    inp.value = box.name;
    inp.addEventListener('input', () => { box.name = inp.value; commitBios(); refreshBioMatches(); });
    const ed = card.querySelector('.ed');
    ed.innerHTML = box.html;
    ed.addEventListener('input', () => { box.html = ed.innerHTML; commitBios(); refreshBioMatches(); });
    const [up, down, del] = card.querySelectorAll('.biohead button');
    up.onclick = () => { if (i > 0) { [bioBoxes[i - 1], bioBoxes[i]] = [bioBoxes[i], bioBoxes[i - 1]]; commitBios(); renderBios(); } };
    down.onclick = () => { if (i < bioBoxes.length - 1) { [bioBoxes[i + 1], bioBoxes[i]] = [bioBoxes[i], bioBoxes[i + 1]]; commitBios(); renderBios(); } };
    del.onclick = () => {
      if (!bioPlain(box.html) || confirm('Remove this contributor bio?')) { bioBoxes.splice(i, 1); commitBios(); renderBios(); }
    };
    c.appendChild(card);
  });
  refreshBioMatches();
}
function addBioBox(){
  if (!bioBoxes) bioBoxes = initialBioBoxes();
  bioBoxes.push({ name: '', html: '' });
  commitBios();
  renderBios();
  const inputs = $$('#biolist .biobox input');
  if (inputs.length) inputs[inputs.length - 1].focus();
}
// the same decision the renderer makes, shown beside each name
function refreshBioMatches(){
  if (!bioBoxes) return;
  const people = splitByline(P.meta.authors || '');
  const filled = [];
  bioBoxes.forEach((b, i) => { if (bioPlain(b.html)) filled.push(i); });
  $$('#biolist .biobox').forEach((card, i) => {
    const span = card.querySelector('.biomatch'), box = bioBoxes[i];
    if (!span || !box) return;
    if (!bioPlain(box.html)) { span.className = 'biomatch'; span.textContent = 'empty \u2014 not used'; return; }
    let who = matchBioName(box.name, people), how = 'name';
    if (who < 0 && people.length === 1 && filled.length === 1) { who = 0; how = 'only'; }
    if (who < 0 && !nameKey(box.name) && filled.length === people.length) { who = filled.indexOf(i); how = 'order'; }
    if (who >= 0 && people[who]) {
      const [s, g] = people[who];
      span.className = 'biomatch ok';
      span.textContent = '\u2713 attached to ' + (g + ' ' + s).trim() + (how === 'order' ? ' (by order)' : '');
    } else {
      span.className = 'biomatch bad';
      span.textContent = people.length ? '\u26a0 no author with this name in the Author(s) field'
                                       : '\u26a0 fill in the Author(s) field first';
    }
  });
}
function wireBios(){
  document.addEventListener('input', e => {
    if (e.target && e.target.closest && e.target.closest('#metafields')) { fillBioDatalist(); refreshBioMatches(); }
  });
}

// ---------- link a citation without leaving the text ----------
// Click into any marked citation in the Body or Notes tab and a bar at the
// foot of the window shows which entry it points at, with the same dropdown
// the Citations tab has. Changing it edits the <cite> in place, so the page
// is not re-rendered and you stay exactly where you were.
let cbTarget = null, cbPointerInBar = false;

function citeBarEl(){
  let bar = document.getElementById('citebar');
  if (bar) return bar;
  bar = document.createElement('div');
  bar.id = 'citebar';
  bar.className = 'citebar';
  bar.style.display = 'none';
  bar.innerHTML = `<div class="cb-row"><span class="cb-label">Citation <b class="cb-text"></b> links to:</span>
      <span class="badge cb-badge"></span></div>
    <div class="cb-row"><select class="cb-select"></select>
      <button type="button" class="small cb-confirm">&#10003; confirm</button>
      <button type="button" class="small ghost cb-review">Citations tab &rarr;</button>
      <button type="button" class="small ghost cb-close" title="hide this bar">&#10005;</button></div>`;
  bar.addEventListener('mouseenter', () => { cbPointerInBar = true; });
  bar.addEventListener('mouseleave', () => { cbPointerInBar = false; });
  const sel = bar.querySelector('.cb-select');
  sel.addEventListener('change', () => {
    const el = cbTarget && cbTarget.isConnected ? cbTarget : null;
    if (!el) { hideCiteBar(); return; }
    el.dataset.rid = sel.value;
    el.dataset.status = sel.value ? 'confirmed' : 'none';
    el.dataset.basis = 'manual';
    syncCiteEd(el);
    fillCiteBar(el);
  });
  bar.querySelector('.cb-confirm').onclick = () => {
    const el = cbTarget && cbTarget.isConnected ? cbTarget : null;
    if (!el) { hideCiteBar(); return; }
    if (!el.dataset.rid) { alert('Pick a Works Cited entry first.'); return; }
    el.dataset.status = 'confirmed';
    syncCiteEd(el);
    fillCiteBar(el);
  };
  bar.querySelector('.cb-review').onclick = () => {
    const el = cbTarget && cbTarget.isConnected ? cbTarget : null;
    const loc = el ? citeLocation(el) : null;
    hideCiteBar();
    if (loc) jumpToCitation(loc.gidx, loc);
  };
  bar.querySelector('.cb-close').onclick = hideCiteBar;
  document.body.appendChild(bar);
  return bar;
}
// write the edited paragraph back into the draft, as typing would
function syncCiteEd(el){
  const ed = el.closest('.ed');
  if (ed && ed.__holder) { ed.__holder.html = ed.innerHTML; markDirty(); }
}
function fillCiteBar(el){
  const bar = citeBarEl();
  const rid = el.dataset.rid || '', status = el.dataset.status || 'none';
  const refs = allRefs();
  let opts = '<option value="">\u2014 not linked \u2014</option>'
    + refs.map(r => `<option value="${escAttr(r.id)}">${escAttr(refPlain(r).slice(0, 90))}</option>`).join('');
  if (rid && !refs.some(r => r.id === rid)) {
    opts += `<option value="${escAttr(rid)}">(${escAttr(rid)} \u2014 no longer in the reference list)</option>`;
  }
  const sel = bar.querySelector('.cb-select');
  sel.innerHTML = opts;
  sel.value = rid;
  const txt = (el.textContent || '').trim();
  bar.querySelector('.cb-text').textContent = '\u201c' + (txt.length > 60 ? txt.slice(0, 57) + '\u2026' : txt) + '\u201d';
  const badge = bar.querySelector('.cb-badge');
  badge.className = 'badge cb-badge b-' + status;
  badge.textContent = status === 'auto' ? 'guessed' : status === 'confirmed' ? 'confirmed' : 'not linked';
}
function showCiteBar(el){
  cbTarget = el;
  fillCiteBar(el);
  citeBarEl().style.display = 'block';
}
function hideCiteBar(){
  cbTarget = null;
  const bar = document.getElementById('citebar');
  if (bar) bar.style.display = 'none';
}
function wireCiteBar(){
  document.addEventListener('selectionchange', () => {
    const bar = document.getElementById('citebar');
    if (cbPointerInBar || (bar && bar.contains(document.activeElement))) return;
    const s = window.getSelection();
    if (!s || !s.rangeCount) return;
    let n = s.getRangeAt(0).startContainer;
    if (n && n.nodeType !== 1) n = n.parentNode;
    const cite = n && n.closest ? n.closest('cite') : null;
    if (cite && cite.closest('.ed') && (cite.closest('#tab-body') || cite.closest('#tab-notes'))) {
      if (cite !== cbTarget) showCiteBar(cite);
    } else if (cbTarget) {
      hideCiteBar();
    }
  });
  $$('.tabs button').forEach(b => b.addEventListener('click', hideCiteBar));
}

// ---------- from the Citations tab back to the text ----------
let citeReturn = null;   // {holder, k}: the citation you left the text from

function jumpToText(holder, k){
  showTab(P.blocks.includes(holder) ? 'body' : 'notes');
  const ed = [...document.querySelectorAll('.ed')].find(e => e.__holder === holder);
  const el = findCiteEl(holder, k);
  const target = el || ed;
  if (!target) return;
  if (el) {
    try { ed.focus({ preventScroll: true }); } catch (e) { try { ed.focus(); } catch (e2) {} }
    try {
      const r = document.createRange();
      r.selectNodeContents(el);
      r.collapse(true);
      const s = window.getSelection();
      s.removeAllRanges();
      s.addRange(r);
    } catch (e) {}
  }
  if (target.scrollIntoView) target.scrollIntoView({ block: 'center', behavior: 'smooth' });
  // a flash that never touches the markup (a class would be saved with it)
  if (target.animate) {
    target.animate([{ backgroundColor: '#ffe58a' }, { backgroundColor: 'transparent' }],
                   { duration: 1800, easing: 'ease-out' });
  }
  if (el) showCiteBar(el);
}

// ---------- init ----------
window.addEventListener('DOMContentLoaded', () => {
  renderMeta(); renderBlocks(); renderNotes(); renderRefs();
  if (P.blocks.some(b => b.kind === 'audio' || b.kind === 'figure')) loadMediaList().then(renderBlocks);
  else loadMediaList();
  $$('.tabs button').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
  wireCiteTips();
  wireCiteBar();
  wireBios();
  showTab('metadata');
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') { e.preventDefault(); saveNow(); }
  });
  setInterval(() => { if (dirty) saveNow(); }, 30000);
  window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
});
"""


@app.route("/edit/<pid>")
def edit(pid):
    try:
        project = load_project(pid)
    except (FileNotFoundError, ValueError):
        return redirect("/?error=That+draft+was+not+found.")
    # drafts from before tables were editable carry them as a JATS string;
    # the editor works on rows and cells (saved on the next Save)
    upgrade_tables(project)
    proj_json = json.dumps(project).replace("</", "<\\/")
    title = title_html(project["meta"].get("title") or "") or "(untitled)"
    warnings_html = ""
    if project.get("warnings"):
        items = "".join(f"<li class='hint'>&#9888; {escape(w)}</li>" for w in project["warnings"])
        warnings_html = f"<div class='card'><b>Notes from the IDML import:</b><ul>{items}</ul></div>"
    body = f"""
<div class="savebar"><span class="status" id="savestatus">saved</span>
<button onclick="saveNow()">Save</button></div>
<h2 style="margin-bottom:0">{title}</h2>
<p class="hint">{escape(project['meta'].get('authors',''))} &middot; {escape(project['meta'].get('section',''))}
&middot; imported from {escape(project.get('source_filename','') or 'scratch')}</p>
{warnings_html}
<div class="tabs">
  <button data-tab="metadata">Metadata</button>
  <button data-tab="body">Body</button>
  <button data-tab="notes">Notes</button>
  <button data-tab="refs">References</button>
  <button data-tab="citations">Citations</button>
  <button data-tab="preview">Preview</button>
  <button data-tab="generate">Generate Files</button>
</div>

<div class="panel" id="tab-metadata">
  <div class="toolbar">
    <button onclick="fmt('italic')"><i>Italic</i></button>
    <button onclick="fmt('bold')"><b>Bold</b></button>
    <span class="hint">Select words in the title, subtitle, or any box below, then click Italic or Bold.</span>
  </div>
  <div class="grid2" id="metafields"></div>
  <label>Keywords (separate with ;)</label><input type="text" id="kw">
  <label>Abstract</label><div class="ed" contenteditable="true" id="meta-abstract"></div>
  <label>Book(s) under review (book reviews only)</label><div class="ed" contenteditable="true" id="meta-bookinfo"></div>
  <label>Acknowledgements</label><div class="ed" contenteditable="true" id="meta-ack"></div>
  <label>Funding</label>
  <p class="hint">Who paid for the research, as printed (e.g. &ldquo;This work was supported by SSHRC&hellip;&rdquo;). Goes into the XML as a funding statement, where Crossref and indexes look for it.</p>
  <div class="ed" contenteditable="true" id="meta-funding"></div>
  <label>Ethics statement</label>
  <p class="hint">Research ethics board approval or similar, as printed. Shown after the Acknowledgements.</p>
  <div class="ed" contenteditable="true" id="meta-ethics"></div>
  <label>Contributor bios (one box per contributor)</label>
  <p class="hint">Type each contributor's name as it appears in the Author(s) field, then paste that person's bio underneath.
  The note beside each name shows which author the bio will be attached to.</p>
  <div id="biolist"></div>
  <button type="button" class="ghost" onclick="addBioBox()">+ Add a contributor</button>
</div>

<div class="panel" id="tab-body">
  <div class="toolbar">
    <button onclick="fmt('italic')"><i>Italic</i></button>
    <button onclick="fmt('bold')"><b>Bold</b></button>
    <button onclick="markCitation()">Mark selection as citation</button>
    <button onclick="linkFigure()">Link to figure</button>
    <button class="ghost" onclick="autoLinkFigures()">Auto-link “Figure N”</button>
  </div>
  <div class="toolbar toolbar2">
    <button onclick="openPlaceAtMention()" title="Move each figure and table to just after the paragraph that first mentions it">Place at first mention</button>
    <button id="undomove" class="ghost" onclick="undoMove()" disabled title="Put the blocks back in the order they were before the last move">Undo move</button>
    <button onclick="insertTable()" title="Insert an empty table below the block you last clicked in">+ Table</button>
    <button class="ghost" onclick="openFindTables()" title="Find paragraphs laid out in columns with tabs and turn them into tables">Find tabbed tables</button>
    <span class="hint">Move any block by dragging its &#10303; handle or with “Move to…”.</span>
  </div>
  <div class="toolbar-hint">
    <span class="hint">Headings = sections in the XML. Yellow = citation guess, green = confirmed, blue = figure link.
    Hover a citation to see the entry it points at,</span>
  </div>
  <div id="blocks"></div>
</div>

<div class="panel" id="tab-notes">
  <div class="toolbar">
    <button onclick="fmt('italic')"><i>Italic</i></button>
    <button onclick="fmt('bold')"><b>Bold</b></button>
    <button onclick="markCitation()">Mark selection as citation</button>
    <button onclick="linkFigure()">Link to figure</button>
    <button onclick="findNoteDois()">Find DOIs on Crossref</button>
    <button class="ghost" onclick="acceptAllStrongNotes()">&#10003; Accept all confident</button>
  </div>
  <div class="toolbar-hint">
    <span class="hint" id="notedoistatus">Find DOIs checks each full citation in the notes (a title and a year);
    short forms and <i>Ibid.</i> are skipped, and so are citations that already carry a DOI.</span>
  </div>
  <div class="toolbar-hint">
    <span class="hint">Notes are numbered by position; drag a note's &#10303; handle to reorder.
    Marked citations appear in the Citations tab like the body's, hovering
    shows the entry it points at.</span>
  </div>
  <div id="notes"></div>
</div>

<div class="panel" id="tab-refs">
  <div class="toolbar">
    <button onclick="fmt('italic')"><i>Italic</i></button>
    <button onclick="findDois()">Find DOIs on Crossref</button>
    <button class="ghost" onclick="acceptAllStrong()">&#10003; Accept all confident</button>
    <span class="hint" id="doistatus">Edit entries exactly as they should display.
    Entries that already carry a DOI are skipped.</span>
  </div>
  <div id="refgroups"></div>
</div>

<div class="panel" id="tab-citations">
  <div class="toolbar">
    <button onclick="confirmAllGuesses()">&#10003; Confirm all guesses</button>
    <button class="ghost" onclick="rescan()">Re-scan text for citations</button>
    <span class="hint" id="citsummary"></span>
  </div>
  <div id="citlist"></div>
</div>

<div class="panel" id="tab-preview"><div class="prev" id="previewbody"></div></div>

<div class="panel" id="tab-generate">
  <p>This saves the draft, builds the JATS 1.4 XML file, and checks it against the DTD.</p>
  <button onclick="generate()">Generate &amp; validate XML</button>
  <div id="genresult"></div>
</div>
<script>window.__PROJECT__ = {proj_json};</script>
<script>{EDITOR_JS}</script>
"""
    html_page = page(f"Edit — {title}", body)
    html_page = html_page.replace("</head>", f"<style>{EDITOR_CSS}</style></head>")
    return html_page


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5002)
