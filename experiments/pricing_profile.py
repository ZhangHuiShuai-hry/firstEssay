"""Instrumentation around immutable V1 PP and persistent V2 PP; no pricing heuristics."""
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code/dwcg'))
import pricing
from persistent_pricing import PersistentPricing


class PricingOracle:
    def __init__(self,version,config,events):
        self.version=version;self.config=config;self.events=events;self.models={};self.records=[]

    def __call__(self,line,station,duals,phase=2,verbose=False):
        begin=time.perf_counter();before=len(self.events)
        record=dict(line=line['id'],station=station,phase=phase,status='unproven',rc=None,
                    build_time=0.,native_creation_time=0.,translation_time=0.,objective_update_time=0.,native_time=0.)
        model=None;record_before=0
        try:
            if self.version=='V1':
                factory=pricing.cbc
                def measured_factory(*args,**kwargs):
                    record['build_time']=time.perf_counter()-begin
                    return factory(*args,**kwargs)
                pricing.cbc=measured_factory
                try:col,rc=pricing.price(line,station,duals,phase,verbose)
                finally:pricing.cbc=factory
            elif self.version=='V2':
                key=(line['id'],station)
                if key not in self.models:
                    path=str(Path(self.config.log_dir)/f'pp_{line["id"]}_{station}.log') if self.config.log_dir else None
                    model=PersistentPricing(line,station,self.config,path);self.models[key]=model
                    record['build_time']=model.structure_seconds;record['native_creation_time']=model.native_creation_seconds
                model=self.models[key];record_before=len(model.records)
                col,rc=model.solve(duals,phase,self.config.deadline)
            else:raise ValueError('PP version must be V1 or V2')
            record.update(rc=rc,status='optimal',assignments=list(col.assignments))
            return col,rc
        finally:
            if self.version=='V1':
                current=[e for e in self.events[before:] if e['role']=='pricing']
                if current:
                    e=current[-1];record.update(native_time=e['solver_time'],translation_time=e['translation_time'],
                                               native_status=e['native_status'],native_status_text=e['native_status_text'])
                    if e['status']=='time_limit':record['status']='time_limit'
            elif model is not None and len(model.records)>record_before:
                e=model.records[-1]
                for k in ('objective_update_time','native_time','native_status','native_status_text','best_bound','nodes','mip_gap'):
                    if k in e:record[k]=e[k]
                record['status']=e['status']
            record['wall_time']=time.perf_counter()-begin
            record['other_time']=record['wall_time']-sum(record[k] for k in ('build_time','native_creation_time','translation_time','objective_update_time','native_time'))
            self.records.append(record)

    def close(self):
        for model in self.models.values():model.close()
