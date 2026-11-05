"""保留全部原始记录，显式标记受干扰组；不复制或替换旧证据。"""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
    initial=json.loads((HERE/'evidence/paired30/accounting.json').read_text(encoding='utf-8'))
    confirm=json.loads((HERE/'evidence/tight_confirm30/accounting.json').read_text(encoding='utf-8'))
    assert len(initial)==20 and len(confirm)==4
    records=[dict(source='evidence/paired30/accounting.json',index=i,eligible_for_performance=i<16,
                  reason='serial performance worker' if i<16 else 'final group conservatively excluded: fault-test overlap',**r)
             for i,r in enumerate(initial)]
    records += [dict(source='evidence/tight_confirm30/accounting.json',index=i,eligible_for_performance=True,
                     reason='serial confirmation without solver tests',**r) for i,r in enumerate(confirm)]
    (HERE/'evidence/formal_index.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print('Eligible:',sum(r['eligible_for_performance'] for r in records),'of',len(records))
if __name__=='__main__':main()
