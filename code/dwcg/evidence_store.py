"""Version 3 lossless Merkle JSON store. SQLite FULL transactions publish roots atomically."""
import hashlib,json,sqlite3,time,zlib,copy

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')

class EvidenceStore:
    def __init__(self,path):
        self.db=sqlite3.connect(str(path));self.seconds=0
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS objects (hash TEXT PRIMARY KEY, payload BLOB NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS roots (seq INTEGER PRIMARY KEY, kind TEXT, hash TEXT, version INTEGER)')
        self.db.commit()
    def put(self,value,kind='result'):
        tick=time.perf_counter();seen=set()
        def encode(v):
            if not isinstance(v,(dict,list,tuple)):return ['scalar',v]
            if isinstance(v,dict) and 'rounds' in v and 'restrictions' in v:
                # Certificate is a compressed chunk. Avoid a SQL object for every tiny
                # assignment/mode container while sharing identical node certificates.
                body=['json',v]
            else:
                body=['dict',[[k,encode(x)] for k,x in sorted(v.items())]] if isinstance(v,dict) else ['list',[encode(x) for x in v]]
            raw=canonical(body);h=hashlib.sha256(raw).hexdigest()
            if h not in seen:
                self.db.execute('INSERT OR IGNORE INTO objects VALUES (?,?)',(h,zlib.compress(raw,1)));seen.add(h)
            return ['ref',h]
        with self.db:
            root=encode(value)
            # Result roots are always containers. Scalars can still be children.
            if root[0]!='ref':raise ValueError('Root must be a JSON container')
            self.db.execute('INSERT INTO roots(kind,hash,version) VALUES (?,?,3)',(kind,root[1]))
        self.seconds+=time.perf_counter()-tick
        return root[1]
    def get(self,kind='result'):
        row=self.db.execute('SELECT hash,version FROM roots WHERE kind=? ORDER BY seq DESC LIMIT 1',(kind,)).fetchone()
        if row is None:raise KeyError(kind)
        if row[1]!=3:raise ValueError('Unsupported storage version')
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
            if body[0]=='json':return copy.deepcopy(body[1])
            if body[0]=='dict':return {k:decode(v) for k,v in body[1]}
            if body[0]=='list':return [decode(v) for v in body[1]]
            raise ValueError('Invalid object type')
        return decode(['ref',row[0]])
    def close(self):self.db.close()

def load_result(path):
    """Legacy JSON and storage v3 share the same hydrated mathematical schema."""
    from pathlib import Path
    path=Path(path)
    if path.suffix!='.sqlite':return json.loads(path.read_text(encoding='utf-8-sig'))
    store=EvidenceStore(path)
    try:return store.get()
    finally:store.close()
