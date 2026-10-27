"""Atomic offline secret-file rotation; execute only on the trusted service host."""
import argparse,json,os,secrets,time,pathlib
p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--serial',required=True);p.add_argument('--overlap-seconds',type=int,default=0);p.add_argument('--lifetime-days',type=int,default=30);a=p.parse_args()
if not 0<=a.overlap_seconds<=3600 or not 1<=a.lifetime_days<=90:p.error('overlap 0..3600 seconds; lifetime 1..90 days')
f=pathlib.Path(a.file);ring=json.loads(f.read_text()) if f.exists() else {};now=time.time();prior=ring.get(a.serial,[])
entries=[dict(root=secrets.token_hex(32),not_after=now+a.lifetime_days*86400)]
if a.overlap_seconds:entries += [dict(root=k['root'],not_after=min(k['not_after'],now+a.overlap_seconds)) for k in prior if k['not_after']>now]
ring[a.serial]=entries;tmp=f.with_name(f.name+'.'+secrets.token_hex(8)+'.tmp')
fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as stream:json.dump(ring,stream,indent=2);stream.flush();os.fsync(stream.fileno())
os.replace(tmp,f)
print('Private keyring rotated. Deliver its current serial root to the authorized SOFTWARE signer through a secure channel; no secret printed.')
