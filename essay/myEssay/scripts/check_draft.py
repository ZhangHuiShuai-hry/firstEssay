"""Evidence, TeX references, template vocabulary and PDF text checks; no solving."""
import hashlib,json,re,sys
from pathlib import Path
from pypdf import PdfReader
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
def main():
    sources=json.loads((HERE/'data/source_manifest.json').read_bytes())
    for path,h in sources.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
    text='\n'.join(p.read_text(encoding='utf-8') for p in [HERE/'HCDP.tex',*sorted((HERE/'sections').glob('*.tex'))])
    refs=set(re.findall(r'\\cite\{([^}]+)\}',text));refs={k for v in refs for k in v.split(',')}
    keys=set(re.findall(r'@\w+\{([^,]+)',(HERE/'MyReferences.bib').read_text()));assert refs==keys and len(keys)==10
    assert not re.search(r'\bthis paper\b|\bwill\b',text,re.I)
    abstract=re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',text,re.S).group(1)
    assert len(re.findall(r'\.(?:\s|$)',abstract))==5
    for f in ('HCDP','HCDP_SF'):
        log=(HERE/'build'/f'{f}.log').read_text(errors='replace')
        assert not re.search(r'undefined|Overfull|Underfull|LaTeX Warning|Package .* Warning',log),f
        reader=PdfReader(HERE/f'{f}.pdf');pdftext='\n'.join(p.extract_text() or '' for p in reader.pages)
        assert len(reader.pages)<=12 if f=='HCDP' else True
        assert 'Author Names and Affiliations to Be Confirmed' in pdftext
        assert '??' not in pdftext
        if f=='HCDP':assert all(f'[{i}]' in pdftext for i in range(1,11))
    formal=json.loads((HERE/'data/formal600.json').read_bytes());assert len(formal)==12
    assert sum(r['proven'] for r in formal if r['method']=='balanced_bound')==6
    assert sum(r['proven'] for r in formal if r['method']=='compact_plain')==0
    small={r['case']:r for r in json.loads((HERE/'data/correctness.json').read_bytes())}
    assert small['gap']['line_lp']==6.5 and small['gap']['integer_lb']==2 and small['gap']['profile_calls']==4
    assert small['lp_yes_ip_no']['status']=='infeasible_proven' and small['lp_yes_ip_no']['profile_calls']==9
    result=dict(status='PASS',source_hashes=len(sources),references=len(keys),abstract_sentences=5,
                pages={f:len(PdfReader(HERE/f'{f}.pdf').pages) for f in ('HCDP','HCDP_SF')},
                scope='archived evidence extraction, source hashes, TeX/PDF text and log checks; not new optimization runs')
    (HERE/'qa').mkdir(exist_ok=True);(HERE/'qa/checks.json').write_text(json.dumps(result,indent=2));print(result)
if __name__=='__main__':main()
