"""Run saved source/layout/PDF-text/collision audits for an existing figure set."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

SKILL=Path('C:/Users/Hrychang/.codex/skills/nature-figure/scripts')


def audit(folder,source=None):
    records=[]
    source=source or Path(__file__).with_name('plot_results.py')
    checked=subprocess.run([sys.executable,str(SKILL/'validate_figure.py'),str(source),'--json'],capture_output=True,text=True)
    (folder/'source_audit.json').write_text(checked.stdout,encoding='utf-8')
    for pdf in sorted(folder.glob('*.pdf')):
        if '.collision-audit' in pdf.name:continue
        collision=pdf.with_suffix('.collision-audit.json')
        result=subprocess.run([sys.executable,str(SKILL/'audit_figure_collisions.py'),str(pdf),
            '--json-out',str(collision),'--overlay-pdf',str(pdf.with_suffix('.collision-audit.pdf'))],capture_output=True,text=True)
        text=subprocess.run([sys.executable,str(SKILL/'audit_pdf_text.py'),str(pdf),'--min-pt','5','--json'],capture_output=True,text=True)
        pdf.with_suffix('.text-audit.json').write_text(text.stdout,encoding='utf-8')
        records.append(dict(figure=pdf.name,collision_exit=result.returncode,text_exit=text.returncode,
                            collision_output=result.stdout,text_error=text.stderr))
    summary=dict(source_exit=checked.returncode,source_error=checked.stderr,figures=records)
    (folder/'AUDIT_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({'source_exit':checked.returncode,'figures':[{k:v for k,v in r.items() if k not in ('collision_output','text_error')} for r in records]},indent=2))
    return not any(r['collision_exit'] or r['text_exit'] for r in records) and checked.returncode==0


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--source',type=Path);a=p.parse_args()
    raise SystemExit(0 if audit(a.folder,a.source) else 1)
