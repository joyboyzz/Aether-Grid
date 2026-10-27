"""Non-destructive online backup. Never overwrites destination or production DB."""
import argparse,sqlite3,hashlib,json
from pathlib import Path

def backup(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if not source.is_file() or destination.exists() or source==destination:raise ValueError('Existing source and a NEW destination required')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(destination) as dst:src.backup(dst)
    with sqlite3.connect(destination) as dst:
        result=dst.execute('PRAGMA integrity_check').fetchone()[0]
        if result!='ok':raise RuntimeError(result)
    return dict(integrity_check=result,sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),destination=str(destination))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args();print(json.dumps(backup(a.source,a.destination),indent=2))
