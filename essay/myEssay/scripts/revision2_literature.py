"""Public Crossref metadata lookup. No private files or manuscript text are sent."""
import concurrent.futures,hashlib,json,re,time,urllib.parse,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
EXTRA={
'Guler2024':'10.1016/j.cie.2024.109898','Xu2021':'10.1016/j.jclepro.2021.129158',
'Parsa2021':'10.1016/j.rcim.2021.102170','Guo2023':'10.1109/TCSS.2022.3217101',
'Wu2023':'10.1016/j.eswa.2023.120589','Xiao2024':'10.1051/mfreview/2024015',
'Yin2025':'10.1016/j.jclepro.2025.144695','Battaia2022':'10.1016/j.ijpe.2022.108673',
'He2024':'10.1016/j.ijpe.2024.109257','Boysen2022':'10.1016/j.ejor.2021.11.043',
'Alfandi2025':'10.1080/00207543.2024.2449241','Fang2024':'10.1080/00207543.2023.2251064',
'Zhu2024':'10.1016/j.cie.2024.110621','Wu2024':'10.1016/j.engappai.2024.108703',
'Xu2024':'10.1016/j.eswa.2023.122323','Pessoa2020':'10.1007/s10107-020-01523-z',
'Barnhart1998':'10.1287/opre.46.3.316','IPCG':'10.1007/s12532-023-00240-w',
'Hazard2024':'10.1016/j.cie.2024.110089','Ozceylan2019':'10.1080/00207543.2018.1428775'}
QUERIES={
'Laili2020':'Model review and algorithm comparison on multi-objective disassembly line balancing',
'duMerle1999':'Stabilized column generation',
'Otto2011':'Incorporating ergonomic risks into assembly line balancing',
'Zhang2025':'Human-Robot Collaborative Disassembly Profit Maximization via Improved Grey Wolf Optimizer'}
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'ManuscriptBibliographyAudit/1.0 (public metadata only)'})
    with urllib.request.urlopen(req,timeout=35) as r:return json.load(r)
def compact_work(record):
    """Retain bibliographic evidence, excluding abstracts and affiliation contacts."""
    fields=('DOI','title','container-title','volume','issue','page','article-number','type',
            'published-print','published-online','published','issued','URL','score')
    result={k:record[k] for k in fields if k in record}
    result['author']=[{k:a[k] for k in ('given','family') if k in a} for a in record.get('author',[])]
    return result
def fetch(item):
    key,doi=item
    try:
        url='https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')
        return key,dict(status='OK',url=url,record=compact_work(get(url)['message']))
    except Exception as e:return key,dict(status='ERROR',doi=doi,error=str(e))
def main():
    folder=HERE/'data/literature_v2';folder.mkdir(exist_ok=True)
    entries={m.group(1):m.group(2) for m in re.finditer(r'@article\{([^,]+),.*?doi=\{([^}]+)\}',(HERE/'MyReferences.bib').read_text(),re.S)}
    entries.update(EXTRA)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:records=dict(pool.map(fetch,entries.items()))
    queries={}
    for key,q in QUERIES.items():
        try:queries[key]=[compact_work(r) for r in get('https://api.crossref.org/works?query.title='+urllib.parse.quote(q)+'&rows=3')['message']['items']]
        except Exception as e:queries[key]=dict(error=str(e))
    (folder/'metadata.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'query_candidates.json').write_text(json.dumps(queries,ensure_ascii=False,indent=2),encoding='utf-8')
    for k,v in records.items():print(k,v['status'],v.get('record',{}).get('title'),flush=True)
    for k,vs in queries.items():
        print('QUERY',k,[(v.get('title'),v.get('DOI')) for v in vs] if isinstance(vs,list) else vs,flush=True)
    # Style exemplars remain temporary, never copied into the manuscript assets.
    dest=HERE/'build/reference_pdfs';dest.mkdir(parents=True,exist_ok=True)
    for name,url in [('57','https://hopeembark.org/index.php/IJGMAI/article/download/57/33/591'),('45','https://hopeembark.org/index.php/IJGMAI/article/download/45/28/581'),('63','https://hopeembark.org/index.php/IJGMAI/article/download/63/41/730')]:
        try:
            with urllib.request.urlopen(url,timeout=30) as r:(dest/(name+'.pdf')).write_bytes(r.read())
        except Exception as e:print('PDF',name,str(e))
if __name__=='__main__':main()
