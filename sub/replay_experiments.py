"""重放 sub 实验：小例完整枚举，中例明确只认证算术/见证及原生求解状态。"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback
import zlib

from validate import audit, check_witness
ROOT=Path(__file__).resolve().parents[1]


def replay(folders):
    spec=importlib.util.spec_from_file_location('_sub_root_verify',ROOT/'docs/root_diagnostics/verify_root.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    from evidence_store import load_result
    records=[]
    for folder in folders:
        folder=folder.resolve()
        for child in sorted(folder.iterdir()):
            if not child.is_dir() or not (child/'summary.json').exists():
                continue
            try:
                summary=json.loads((child/'summary.json').read_text(encoding='utf-8'))
                raw=(child/'instance.json').read_bytes()
                assert hashlib.sha256(raw).hexdigest()==summary['input_sha256']
                compressed=(child/'result.json.zlib').read_bytes()
                assert hashlib.sha256(compressed).hexdigest()==summary['evidence_sha256']
                data=json.loads(raw.decode('utf-8-sig'))
                result=json.loads(zlib.decompress(compressed))
                tiny=sum(len(l['tasks']) for l in data['lines'])<=6
                if summary['method']=='line':
                    checked=audit(data,result,enumerate_pricing=tiny)
                elif summary['method']=='compact':
                    if result['witness']:
                        check_witness(data,result['witness'],result['global_lower_bound'])
                    info=result.get('solver_result')
                    if result['global_integer_optimal_proven']:
                        assert info['optimal'] and result['witness']
                    if result['global_upper_bound'] is not None:
                        assert info['best_bound']==result['global_upper_bound']
                    checked=dict(status='PASS',scope='independent_original_witness_and_native_bound_metadata')
                else:
                    original=load_result(child/'certificate.sqlite')
                    checked=module.verify(data,original,tiny)
                    checked['status']='PASS'
                records.append(dict(path=str(child.relative_to(ROOT)),**checked))
            except Exception as error:
                records.append(dict(path=str(child.relative_to(ROOT)),status='FAIL',
                                    error=repr(error),traceback=traceback.format_exc()))
    return records


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('folders',nargs='+',type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args(); result=replay(args.folders)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(total=len(result),passed=sum(e['status']=='PASS' for e in result),
                          failed=[e['path'] for e in result if e['status']=='FAIL']),ensure_ascii=False))
