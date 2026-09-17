"""Closed result-file contract for #345; no market reader or execution capability."""
import gzip
import hashlib
import json
import re
from pathlib import Path
from wave_recognizer_r3_v1_entry import encode

MAX_ROWS = 70114
MAX_TRACE_BYTES = 128 * 1024**2
MAX_TOTAL_BYTES = 64 * 1024**2
FIXED = {'report.json':2000000, 'manifest.json':500000,
         'events.json':8000000, 'latency.json':2000000,
         'trace.jsonl.gz':16*1024**2, 'parent/report.json':2000000,
         'parent/manifest.json':500000, 'visuals/index.json':2000000}
SVG = re.compile(r'visuals/case-[0-9a-f]{16}-[0-9]{1,3}\.svg\Z')

def no_links(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in [path, *path.parents]):
        raise ValueError('symlink not permitted')
    return path

def file_limit(name):
    if name in FIXED:
        return FIXED[name]
    if SVG.fullmatch(name):
        return 250000
    raise ValueError('file outside closed output contract')

def fresh_root(path):
    path = no_links(path)
    if not path.parent.is_dir():
        raise ValueError('output parent must already exist')
    path.mkdir(mode=0o700)
    return path

def write_bytes(root, name, raw):
    limit = file_limit(name)
    if not isinstance(raw, bytes) or len(raw)>limit:
        raise ValueError('output byte limit')
    target = no_links(Path(root)/name)
    with target.open('xb') as stream:
        stream.write(raw)

def read_bytes(root, name):
    limit = file_limit(name)
    target = no_links(Path(root)/name)
    if not target.is_file() or target.stat().st_size>limit:
        raise ValueError('input result byte limit')
    with target.open('rb') as stream:
        raw = stream.read(limit+1)
    if len(raw)>limit:
        raise ValueError('input result grew beyond limit')
    return raw

def unique_object(pairs):
    obj = {}
    for key,value in pairs:
        if key in obj:
            raise ValueError('duplicate JSON key')
        obj[key] = value
    return obj

def decode(raw):
    def invalid(value):
        raise ValueError('nonfinite JSON value')
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=invalid)

def read_json(root,name):
    return decode(read_bytes(root,name))

def write_trace(root, rows):
    if not 0<len(rows)<=MAX_ROWS:
        raise ValueError('trace row bound')
    size = 0
    path = no_links(Path(root)/'trace.jsonl.gz')
    with path.open('xb') as sink:
        with gzip.GzipFile(filename='',mode='wb',fileobj=sink,mtime=0) as stream:
            for row in rows:
                raw = encode(row)
                size += len(raw)
                if len(raw)>8192 or size>MAX_TRACE_BYTES:
                    raise ValueError('uncompressed trace bound')
                stream.write(raw)
        if sink.tell()>FIXED['trace.jsonl.gz']:
            raise ValueError('compressed trace bound')

def read_trace(root):
    path = no_links(Path(root)/'trace.jsonl.gz')
    if not path.is_file() or path.stat().st_size>FIXED['trace.jsonl.gz']:
        raise ValueError('compressed trace bound')
    rows = []
    size = 0
    with gzip.open(path,'rb') as stream:
        while True:
            raw = stream.readline(8193)
            if not raw:
                break
            size += len(raw)
            if len(raw)>8192 or not raw.endswith(b'\n') or size>MAX_TRACE_BYTES or len(rows)>=MAX_ROWS:
                raise ValueError('decoded trace bound')
            rows.append(decode(raw))
    if not rows:
        raise ValueError('empty trace')
    return rows

def inventory(root):
    root = no_links(root)
    if not root.is_dir():
        raise ValueError('missing result directory')
    answer = {}
    total = pages = 0
    for path in root.rglob('*'):
        no_links(path)
        name = path.relative_to(root).as_posix()
        if path.is_dir():
            if name not in ('parent','visuals'):
                raise ValueError('unexpected output directory')
            continue
        raw = read_bytes(root,name)
        total += len(raw)
        pages += bool(SVG.fullmatch(name))
        if total>MAX_TOTAL_BYTES or pages>1000:
            raise ValueError('result budget exceeded')
        if name!='manifest.json':
            answer[name] = {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if not set(FIXED).difference({'manifest.json'}).issubset(answer):
        raise ValueError('incomplete result set')
    return dict(sorted(answer.items()))

def write_manifest(root):
    write_bytes(root,'manifest.json',encode({'schema_id':'csi1000.r3_clock_files@1.0',
        'files':inventory(root),'new_training':False,'production_authority':False}))

def verify_manifest(root):
    m = read_json(root,'manifest.json')
    if set(m)!={'schema_id','files','new_training','production_authority'} or m['schema_id']!='csi1000.r3_clock_files@1.0':
        raise ValueError('manifest schema drift')
    if m['new_training'] is not False or m['production_authority'] is not False or m['files']!=inventory(root):
        raise ValueError('manifest content drift')
    return m
