"""Build the added references from saved public DOI metadata; never infer entries."""
import html,json,re,unicodedata
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]

def tex(s):
    s=html.unescape(re.sub('<[^>]+>','',s)).replace('–','--').replace('—','---').replace('&',r'\&')
    marks={'\u0308':'"','\u0301':"'",'\u0300':'`','\u0302':'^','\u0303':'~','\u0327':'c'}
    out=[]
    for c in s:
        if ord(c)<128:out.append(c);continue
        parts=unicodedata.normalize('NFD',c)
        if len(parts)==2 and parts[1] in marks:out.append('{\\'+marks[parts[1]]+'{'+parts[0]+'}}')
        else:out.append({'ı':r'{\i}','ł':r'{\l}','’':"'",'−':'-'}.get(c,c))
    return ''.join(out)

def main():
    db=json.loads((HERE/'data/literature_v2/metadata.json').read_text(encoding='utf-8'))
    queries=json.loads((HERE/'data/literature_v2/query_candidates.json').read_text(encoding='utf-8'))
    original=(HERE/'MyReferences.bib').read_text(encoding='utf-8').split('% Added references')[0].rstrip()
    existing=set(re.findall(r'@article\{([^,]+)',original))
    rename={'IPCG':'Maher2023','Hazard2024':'GoksoyKalaycilar2024'}
    records={rename.get(k,k):v['record'] for k,v in db.items() if v['status']=='OK'}
    reviewed={'Laili2020':'10.1016/j.jmsy.2020.07.015','duMerle1999':'10.1016/s0012-365x(98)00213-1',
              'Otto2011':'10.1016/j.ejor.2011.01.056','Zhang2025':'10.67119/6413dhny'}
    for k,doi in reviewed.items():
        vs=queries[k];assert isinstance(vs,list) and vs
        matches=[v for v in vs if v['DOI'].lower()==doi.lower()]
        assert len(matches)==1,(k,doi)
        records[k]=matches[0]
    additions=[];rows=[]
    for key,r in records.items():
        if key in existing:continue
        authors=[]
        for a in r['author']:
            family,given=a['family'],a.get('given','')
            if family=='Ali Ilgin':family,given='Ilgin','Mehmet Ali'
            # BibTeX comma syntax preserves multiword surnames and particles.
            authors.append(tex(family)+', '+tex(given))
        date=r.get('published-print',r.get('published',r['issued']))['date-parts'][0][0]
        if key=='Zhang2025':date=2025
        pages=r.get('page',r.get('article-number','')).replace('-', '--')
        if key=='Zhang2025':pages='69--79'
        fields={'author':' and '.join(authors),'title':tex(r['title'][0]),'journal':tex(r['container-title'][0]),
                'volume':r.get('volume',''),'number':r.get('issue',''),'pages':pages,'year':str(date),'doi':r['DOI']}
        # Protect letter case in IEEE bibliography styles without changing titles.
        fields['title']='{'+fields['title']+'}'
        additions.append('@article{'+key+',\n'+',\n'.join(' '+k+'={'+v+'}' for k,v in fields.items() if v)+'}\n')
    (HERE/'MyReferences.bib').write_text(original+'\n\n% Added references: DOI metadata audited 2026-11-07.\n'+ '\n'.join(additions),encoding='utf-8')
    for key in sorted(existing|set(records)):
        r=records.get(key)
        if r:rows.append(dict(key=key,doi=r['DOI'],title=r['title'][0],source='https://doi.org/'+r['DOI'],status='public DOI metadata retrieved'))
        elif key=='Guo2024a':rows.append(dict(key=key,doi='10.1109/TASE.2023.3296733',status='prior verified entry retained; current API retry unavailable'))
    (HERE/'data/literature_v2/verified_index.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Total references:',len(rows),'Added:',len(additions))
if __name__=='__main__':main()
