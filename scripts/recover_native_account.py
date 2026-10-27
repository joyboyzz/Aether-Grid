"""Break-glass local recovery. Requires trusted host access and a stopped service."""
import argparse,sqlite3,pathlib,getpass,hashlib,base64,secrets,json,time
p=argparse.ArgumentParser();p.add_argument('database');p.add_argument('--username',required=True);p.add_argument('--service-stopped',action='store_true');a=p.parse_args()
if not a.service_stopped:p.error('Stop service, back up DB, then explicitly acknowledge --service-stopped')
f=pathlib.Path(a.database).resolve()
if not f.is_file():raise SystemExit('Existing DB required')
pw=getpass.getpass('New password (16+ chars): ')
if len(pw)<16 or pw!=getpass.getpass('Repeat password: '):raise SystemExit('Mismatch or too short')
salt=secrets.token_bytes(16);encoded='pbkdf2-sha256$210000$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(hashlib.pbkdf2_hmac('sha256',pw.encode(),salt,210000)).decode()
with sqlite3.connect(f) as c:
 c.execute('BEGIN IMMEDIATE');r=c.execute("select json from documents where kind='user' and id=?",(a.username,)).fetchone()
 if not r:raise SystemExit('No such account')
 u=json.loads(r[0]);u.update(password_hash=encoded,version=u.get('version',1)+1)
 # Deliberately do not silently enable disabled accounts or change roles.
 c.execute("update documents set json=? where kind='user' and id=?",(json.dumps(u),a.username))
 c.execute("delete from documents where kind='session' and json_extract(json,'$.username')=?",(a.username,))
 c.execute("insert into outbox(event,batch_id,json,created_at) values('local_password_recovery',?,?,datetime('now'))",(a.username,json.dumps(dict(subject=a.username,local_host_assertion=True))))
print('Password reset, sessions revoked, audit recorded. Disabled flag and role unchanged. Restart service only after review.')
