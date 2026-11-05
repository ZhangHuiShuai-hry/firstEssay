import json,sys,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from validate import enumerate_all,solve_full
def main():
    rows=[]
    for path in sorted((HERE/'evidence/inputs').glob('tasks*.json')):
        d=json.loads(path.read_bytes());full=enumerate_all(d)
        lp=solve_full(d,full);ip=solve_full(d,full,True)
        assert lp['optimal'] and ip['optimal'] and lp['objective']>ip['objective']+1e-5
        rows.append(dict(input=path.name,input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),LP=lp,IP=ip,counts={l:len(c) for l,c in full.items()}))
    with (HERE/'evidence/input_oracles.json').open('x',encoding='utf-8') as f:json.dump(rows,f,indent=2)
    print([(r['input'],r['LP']['objective'],r['IP']['objective']) for r in rows])
if __name__=='__main__':main()
