"""Schema 4 incremental Merkle store; lossless schema 3 reader compatibility."""
import hashlib,json,sqlite3,time,zlib,copy

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')

class EvidenceStore:
    def __init__(self,path):
        self.db=sqlite3.connect(str(path));self.seconds=0;self.pool_heads={};self.timings=dict(serialize_hash=0.,compress=0.,sql_execute=0.,commit=0.,other=0.)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS objects (hash TEXT PRIMARY KEY, payload BLOB NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS roots (seq INTEGER PRIMARY KEY, kind TEXT, hash TEXT, version INTEGER)')
        self.db.commit()
    def put(self,value,kind='result'):
        tick=time.perf_counter();seen=set();staged={};parts=dict(serialize_hash=0.,compress=0.,sql_execute=0.,commit=0.)
        def save(body):
            t=time.perf_counter()
            raw=canonical(body);h=hashlib.sha256(raw).hexdigest()
            parts['serialize_hash']+=time.perf_counter()-t
            if h not in seen:
                t=time.perf_counter();compressed=zlib.compress(raw,1);parts['compress']+=time.perf_counter()-t
                t=time.perf_counter();self.db.execute('INSERT OR IGNORE INTO objects VALUES (?,?)',(h,compressed));parts['sql_execute']+=time.perf_counter()-t;seen.add(h)
            return ['ref',h]
        def encode(v):
            from incremental_evidence import PoolView,PrimalView
            if isinstance(v,PrimalView):return save(['primal',encode(v.pool),v.coordinates,v.weights])
            if isinstance(v,PoolView):
                blocks=[]
                for key,n in v.counts:
                    cachekey=(v.ledger,key)
                    if cachekey not in staged:staged[cachekey]=list(self.pool_heads.get(cachekey,[]))
                    heads=staged[cachekey]
                    for assignments in v.ledger.columns[key][len(heads):n]:
                        heads.append(save(['column_link',heads[-1] if heads else None,assignments])[1])
                    blocks.append([*key,heads[n-1] if n else None,n])
                return save(['pool_view',blocks])
            if not isinstance(v,(dict,list,tuple)):return ['scalar',v]
            if isinstance(v,dict) and isinstance(v.get('pool'),PoolView):
                return save(['round',encode(v['pool']),encode(v['solution']) if 'solution' in v else None,{k:x for k,x in v.items() if k not in ('pool','solution')}])
            if isinstance(v,dict) and 'rounds' in v and 'restrictions' in v and any(isinstance(r.get('pool'),PoolView) for r in v['rounds']):
                return save(['certificate',encode({k:x for k,x in v.items() if k!='rounds'}),[encode(r) for r in v['rounds']]])
            if isinstance(v,dict) and 'rounds' in v and 'restrictions' in v and not any(isinstance(r.get('pool'),PoolView) for r in v['rounds']):
                # Certificate is a compressed chunk. Avoid a SQL object for every tiny
                # assignment/mode container while sharing identical node certificates.
                body=['json',v]
            else:
                body=['dict',[[k,encode(x)] for k,x in sorted(v.items())]] if isinstance(v,dict) else ['list',[encode(x) for x in v]]
            return save(body)
        with self.db:
            root=encode(value)
            # Result roots are always containers. Scalars can still be children.
            if root[0]!='ref':raise ValueError('Root must be a JSON container')
            self.db.execute('INSERT INTO roots(kind,hash,version) VALUES (?,?,4)',(kind,root[1]))
            commit_started=time.perf_counter()
        parts['commit']=time.perf_counter()-commit_started
        self.pool_heads.update(staged)
        elapsed=time.perf_counter()-tick;self.seconds+=elapsed
        parts['other']=elapsed-sum(parts.values())
        for key,value in parts.items():self.timings[key]+=value
        return root[1]
    def get(self,kind='result'):
        row=self.db.execute('SELECT hash,version FROM roots WHERE kind=? ORDER BY seq DESC LIMIT 1',(kind,)).fetchone()
        if row is None:raise KeyError(kind)
        if row[1] not in (3,4):raise ValueError('Unsupported storage version')
        bodies={}
        def decode(tag):
            if tag[0]=='scalar':return tag[1]
            if tag[0]!='ref':raise ValueError('Invalid reference tag')
            if tag[1] not in bodies:
                record=self.db.execute('SELECT payload FROM objects WHERE hash=?',(tag[1],)).fetchone()
                if record is None:raise ValueError('Missing evidence object')
                raw=zlib.decompress(record[0])
                if hashlib.sha256(raw).hexdigest()!=tag[1]:raise ValueError('Evidence hash mismatch')
                bodies[tag[1]]=json.loads(raw)
            body=bodies[tag[1]]
            if body[0]=='round':
                result=copy.deepcopy(body[-1]);result['pool']=decode(body[1])
                if len(body)==4 and body[2] is not None:result['solution']=decode(body[2])
                return result
            if body[0]=='primal':
                pool={(b['line'],b['station']):b['patterns'] for b in decode(body[1])}
                if len(body[2])!=len(body[3]):raise ValueError('Invalid primal vector length')
                return [dict(line=l,station=s,column=p,assignments=copy.deepcopy(pool[l,s][p]),weight=w) for (l,s,p),w in zip(body[2],body[3])]
            if body[0]=='certificate':
                result=decode(body[1]);result['rounds']=[decode(x) for x in body[2]];return result
            if body[0]=='pool_view':
                blocks=[]
                for l,s,head,n in body[1]:
                    if type(n)!=int or n<0:raise ValueError('Invalid column count')
                    patterns=[]
                    for _ in range(n):
                        if head is None:raise ValueError('Missing column prefix')
                        link=load_body(head)
                        if link[0]!='column_link':raise ValueError('Invalid column link')
                        patterns.append(copy.deepcopy(link[2]));head=link[1]
                    if head is not None:raise ValueError('Invalid column prefix length')
                    blocks.append(dict(line=l,station=s,patterns=list(reversed(patterns))))
                return blocks
            if body[0]=='json':return copy.deepcopy(body[1])
            if body[0]=='dict':return {k:decode(v) for k,v in body[1]}
            if body[0]=='list':return [decode(v) for v in body[1]]
            raise ValueError('Invalid object type')
        def load_body(h):
            if h not in bodies:
                r=self.db.execute('SELECT payload FROM objects WHERE hash=?',(h,)).fetchone()
                if r is None:raise ValueError('Missing column object')
                raw=zlib.decompress(r[0])
                if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('Column hash mismatch')
                bodies[h]=json.loads(raw)
            return bodies[h]
        return decode(['ref',row[0]])
    def close(self):self.db.close()

def load_result(path):
    """Legacy JSON and storage schemas 3/4 share the hydrated mathematical schema."""
    from pathlib import Path
    path=Path(path)
    if path.suffix!='.sqlite':return json.loads(path.read_text(encoding='utf-8-sig'))
    store=EvidenceStore(path)
    try:return store.get()
    finally:store.close()
