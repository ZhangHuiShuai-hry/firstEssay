"""Evidence, TeX references, template vocabulary and PDF text checks; no solving."""
import csv,hashlib,json,re,sys
from pathlib import Path
from pypdf import PdfReader
import pymupdf
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
def main():
    sources=json.loads((HERE/'data/source_manifest.json').read_bytes())
    for path,h in sources.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
    text='\n'.join(p.read_text(encoding='utf-8') for p in [HERE/'HCDP.tex',*sorted((HERE/'sections').glob('*.tex'))])
    refs=set(re.findall(r'\\cite\{([^}]+)\}',text));refs={k for v in refs for k in v.split(',')}
    keys=set(re.findall(r'@\w+\{([^,]+)',(HERE/'MyReferences.bib').read_text()));assert refs==keys and len(keys)>30
    assert not re.search(r'\bthis paper\b|\bwill\b',text,re.I)
    assert not re.search(r'reinforcement|learning-assisted|trained learning',text,re.I)
    intro=(HERE/'sections/introduction.tex').read_text(encoding='utf-8-sig')
    assert 'This work makes the following new contributions:' in intro
    assert intro.count(r'\item ')==3
    model=(HERE/'sections/model.tex').read_text(encoding='utf-8-sig')
    assert r'\input{tables/notation}' not in model
    for key in ('assign','required','prec','cycle','active','hlogic','rlogic','fatigue','sharedh','sharedr','recovery','binary'):
        assert model.count('Constraint~\\eqref{eq:'+key+'}')==1,key
    abstract=re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',text,re.S).group(1)
    assert len(re.findall(r'\.(?:\s|$)',abstract))==5
    for f in ('HCDP','HCDP_SF'):
        log=(HERE/'build'/f'{f}.log').read_text(errors='replace')
        assert not re.search(r'undefined|Overfull|Underfull|LaTeX Warning|Package .* Warning',log),f
        reader=PdfReader(HERE/f'{f}.pdf');pdftext='\n'.join(p.extract_text() or '' for p in reader.pages)
        assert len(reader.pages)<=12 if f=='HCDP' else True
        assert 'Author Names and Affiliations to Be Confirmed' in pdftext
        assert '??' not in pdftext
        if f=='HCDP':assert all(f'[{i}]' in pdftext for i in range(1,len(keys)+1))
    doc=pymupdf.open(HERE/'HCDP.pdf');start=None
    for i,p in enumerate(doc):
        for b in p.get_text('blocks'):
            if 'II. PROBLEM DESCRIPTION' in b[4]:start=dict(page=i+1,x=b[0],y=b[1],page_height=p.rect.height)
    assert start and start['page']==2 and start['y']>start['page_height']/2,start
    assert (HERE/'img/algorithm_flowchart.mmd').is_file()
    for name in ('product_structure','circular_lines','and_mode_or','algorithm_flowchart','performance_lines'):
        for suffix in ('pdf','svg','tiff','png'):assert (HERE/f'img/{name}.{suffix}').is_file()
        audit=json.loads((HERE/f'qa/figures/{name}_collisions.json').read_text(encoding='utf-8-sig'))
        assert audit['verdict']=='PASS',name
        font=json.loads((HERE/f'qa/figures/{name}_text.json').read_text(encoding='utf-8-sig'))
        assert font['minimum_found_pt']>=9.9 and font['below_minimum_count']==0,name
    assert json.loads((HERE/'qa/figures/performance_lines_alignment.json').read_text())['verdict']=='PASS'
    formal=json.loads((HERE/'data/formal600.json').read_bytes());assert len(formal)==12
    with (HERE/'data/performance_lines.csv').open(newline='') as f:plotrows=list(csv.DictReader(f))
    assert len(plotrows)==len(formal)
    expected={(r['case'],r['method']):r for r in formal}
    for r in plotrows:
        original=expected[r['case'],r['method']]
        assert float(r['seconds'])==original['seconds']
        assert abs(float(r['relative_gap_percent'])-100*original['relative_gap'])<1e-12
        assert (r['integer_optimal_proven']=='True')==original['proven']
    assert sum(r['proven'] for r in formal if r['method']=='balanced_bound')==6
    assert sum(r['proven'] for r in formal if r['method']=='compact_plain')==0
    small={r['case']:r for r in json.loads((HERE/'data/correctness.json').read_bytes())}
    assert small['gap']['line_lp']==6.5 and small['gap']['integer_lb']==2 and small['gap']['profile_calls']==4
    assert small['lp_yes_ip_no']['status']=='infeasible_proven' and small['lp_yes_ip_no']['profile_calls']==9
    result=dict(status='PASS',revision=2,source_hashes=len(sources),references=len(keys),abstract_sentences=5,introduction_end=start,
                pages={f:len(PdfReader(HERE/f'{f}.pdf').pages) for f in ('HCDP','HCDP_SF')},
                scope='archived evidence extraction, source hashes, TeX/PDF text and log checks; not new optimization runs')
    (HERE/'qa').mkdir(exist_ok=True);(HERE/'qa/checks.json').write_text(json.dumps(result,indent=2));print(result)
if __name__=='__main__':main()
