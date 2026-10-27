"""One-shot monitor suitable for a scheduler; uses an operator bearer credential file."""
import argparse,pathlib,httpx,json,sys,datetime
p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--token-file',required=True);a=p.parse_args()
try:
 r=httpx.get(a.url.rstrip('/')+'/api/admin/readiness',headers={'Authorization':'Bearer '+pathlib.Path(a.token_file).read_text().strip()},timeout=15);r.raise_for_status();d=r.json();print(json.dumps(dict(timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),status=d['status'],alerts=d['alerts'],database=d['database'])));sys.exit(1 if d['alerts'] else 0)
except Exception as e:
 print(json.dumps(dict(status='monitor_failure',error_type=type(e).__name__)));sys.exit(2)
