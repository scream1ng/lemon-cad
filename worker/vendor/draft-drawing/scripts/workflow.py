#!/usr/bin/env python3
"""draft-drawing workflow.

  preview  STEP OUT   measure the STEP, write OUT/measure.json, OUT/drawing.json (settings, created once), OUT/preview.html
  finalize OUT --request "<user's words>"   write OUT/<title>.pdf from exactly what was previewed

finalize refuses when the STEP file or drawing.json changed after the last preview.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

import measure
import preview
import sheet

DEFAULTS = {'title': '', 'material': 'Steel', 'density_kg_m3': measure.STEEL_KG_M3, 'show_hidden': False, 'scales': {}, 'notes': [], 'skip_items': []}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def settings_of(out, step):
    path = out / 'drawing.json'
    if not path.exists():
        stem = Path(step).stem
        path.write_text(json.dumps({**DEFAULTS, 'title': stem}, indent=1, ensure_ascii=False) + '\n')
    return {**DEFAULTS, **json.loads(path.read_text())}


def render(step, out):
    s = settings_of(out, step)
    result = measure.measure(step, s['density_kg_m3'])
    return result, s, sheet.draw(result, s)


def cmd_preview(step, out):
    out.mkdir(parents=True, exist_ok=True)
    result, s, pages = render(step, out)
    try:
        html, size = preview.inline_html(preview.scene(result, sheet.to_svgs(pages), s))
    finally:
        sheet.close(pages)
    (out / 'measure.json').write_text(json.dumps(measure.public(result), indent=1, ensure_ascii=False) + '\n')
    (out / 'preview.html').write_text(html)
    state = {'step': str(Path(step).resolve()), 'step_sha256': result['source']['sha256'], 'drawing_sha256': digest(out / 'drawing.json'),
             'previewed_at': dt.datetime.now().isoformat(timespec='seconds'), 'pages': len(pages), 'html_bytes': size}
    (out / 'preview-state.json').write_text(json.dumps(state, indent=1) + '\n')
    summary = {'total_mass_kg': result['total_mass_kg'], 'items': [(r['item'], r['description'], r['role'], r['qty'], r['mass_total_kg']) for r in result['items']],
               'unknowns': {r['item']: [u['what'] for u in r.get('unknowns', [])] for r in result['items'] if r.get('unknowns')},
               'pages': len(pages), 'html_bytes': size, 'soft_target_met': size <= preview.INLINE_HTML_TARGET, 'preview': str(out / 'preview.html')}
    print(json.dumps(summary, indent=1, ensure_ascii=False))


def cmd_finalize(out, request):
    if not request.strip(): raise SystemExit('finalize needs --request with the user\'s own words asking for the PDF')
    state_path = out / 'preview-state.json'
    if not state_path.exists(): raise SystemExit('No preview found; run preview first')
    state = json.loads(state_path.read_text())
    if digest(state['step']) != state['step_sha256']: raise SystemExit('STEP file changed since the preview; run preview again')
    if digest(out / 'drawing.json') != state['drawing_sha256']: raise SystemExit('drawing.json changed since the preview; run preview again')
    result, s, pages = render(state['step'], out)
    pdf = out / f"{s['title'] or 'drawing'}.pdf"
    try:
        sheet.to_pdf(pages, pdf, {'Title': s['title'], 'Subject': f"Draft from STEP sha256 {state['step_sha256']}", 'Creator': 'draft-drawing'})
    finally:
        sheet.close(pages)
    (out / 'finalize.json').write_text(json.dumps({'pdf': str(pdf), 'pdf_sha256': digest(pdf), 'step_sha256': state['step_sha256'],
        'drawing_sha256': state['drawing_sha256'], 'request': request, 'at': dt.datetime.now().isoformat(timespec='seconds')}, indent=1) + '\n')
    print(pdf)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('preview'); p.add_argument('step'); p.add_argument('out', type=Path)
    f = sub.add_parser('finalize'); f.add_argument('out', type=Path); f.add_argument('--request', required=True)
    a = ap.parse_args()
    cmd_preview(a.step, a.out) if a.cmd == 'preview' else cmd_finalize(a.out, a.request)
