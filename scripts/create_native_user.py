"""Create a NEW private bootstrap file, never place plaintext passwords in source."""
import argparse,getpass,hashlib,secrets,base64,json,os
p=argparse.ArgumentParser();p.add_argument('destination');p.add_argument('--username',required=True);p.add_argument('--role',choices=['operator','auditor','buyer'],default='operator');p.add_argument('--buyer-id');a=p.parse_args()
if a.role=='buyer' and not a.buyer_id:p.error('--buyer-id required')
pw=getpass.getpass('New password (16+ characters): ')
if len(pw)<16 or pw!=getpass.getpass('Repeat password: '):raise SystemExit('Password too short or mismatch')
salt=secrets.token_bytes(16);encoded='pbkdf2-sha256$210000$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(hashlib.pbkdf2_hmac('sha256',pw.encode(),salt,210000)).decode()
fd=os.open(a.destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:json.dump([dict(username=a.username,role=a.role,buyer_id=a.buyer_id or '',password_hash=encoded)],f,indent=2)
print('Private hashed bootstrap created. Existing database accounts are not overwritten.')
