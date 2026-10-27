"""One-time reviewed cleanup for the inspected project workspace; dry-run by default.
Not an operational retention tool. --apply deletes only the enumerated generated/
legacy candidates beneath this repository after writing their audit manifest.
"""
import argparse,pathlib,hashlib,json,shutil,sqlite3,os
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'verification/final';OUT.mkdir(parents=True,exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
roots={}
def add(path,reason):
 path=ROOT/path
 if path.exists():
  assert path.resolve().is_relative_to(ROOT) and path!=ROOT and not path.is_symlink()
  roots[path]=reason
for x in ['.server-build','.publish-v4','.runtime','.v3-private','.v4-private','.acceptance-private','wwwroot','frontend/node_modules','frontend/dist']:
 add(x,'Reproducible build/dependencies or explicitly synthetic private test state; source and evidence preserved')
for x in ['paper/figures','paper/deck_figures','paper/deck_figures.py','paper/generate_figures.py','paper/evidence_data.py']:
 add(x,'Replaced legacy publication builder/assets; current common builder reproduces corrected project documents')
add('verification/pdf_qa','Superseded PDF intermediate renders; current document QA retained')
add('verification/final/document-qa/office','Intermediate PPT-to-PDF render; final PDFs, editable PPTX, render checks and cover image retained')
for path in ROOT.rglob('*'):
 if any(path==r or r in path.parents for r in roots):continue
 if path.is_dir() and path.name in {'bin','obj','__pycache__','.pytest_cache'}:add(path.relative_to(ROOT),'Generated compiler/cache directory; reproducible from source')
for path in list(ROOT.rglob('*')):
 if any(path==r or r in path.parents for r in roots):continue
 if not path.is_file():continue
 rel=path.relative_to(ROOT);reason=None
 if path.suffix.lower()=='.md' and rel.as_posix()!='README.md':reason='Consolidated into the single current README; obsolete/contradictory claims superseded explicitly'
 elif path.suffix=='.zip' and len(rel.parts)==1:reason='Obsolete release archive; current cleaned source package will replace it after verification'
 elif path.suffix in {'.db','.pyc','.tsbuildinfo'} or path.name.endswith(('.db-wal','.db-shm')):reason='Inspected local demo/test database or generated cache; no operational database in this workspace'
 elif rel.as_posix() in ['frontend/vite.config.js','frontend/vite.config.d.ts']:reason='Generated TypeScript config output; editable vite.config.ts preserved'
 elif rel.as_posix()=='verification/AetherGrid_3min_walkthrough.webm':
  assert (ROOT/'verification/AetherGrid_3min_walkthrough.mp4').exists();reason='Redundant raw recording; finalized historical MP4 and metadata preserved'
 elif len(rel.parts)>=3 and rel.parts[0]=='verification' and rel.parts[1] in {'v3','v4'} and path.name.startswith('portal-') and path.suffix=='.png':reason='Redundant older portal captures; current five-portal and role-journey captures preserved'
 elif rel.parts[:2]==('verification','screenshots') and path.name.startswith('video-'):reason='Intermediate video frame; finished historical MP4 and substantive state screenshots preserved'
 elif path.name in {'browser-install.log','browser-deps.log','npm-install.log'} and rel.parts[0]=='verification':reason='Dependency installation progress log; build/test/audit results retained'
 elif rel.as_posix()=='verification/pdf_structural_qa.json':reason='Superseded by current complete PDF/PPTX QA under verification/final/document-qa'
 if reason:add(rel,reason)
# Eliminate children of already selected directories.
selected=[x for x in sorted(roots,key=lambda p:(len(p.parts),str(p))) if not any(parent in roots for parent in x.parents)]
entries=[];total=0;count=0
for root in selected:
 files=sorted(root.rglob('*')) if root.is_dir() else [root];records=[]
 for f in files:
  if f.is_file():
   data=os.readlink(f).encode() if f.is_symlink() else f.read_bytes();size=f.lstat().st_size;records.append(dict(path=str(f.relative_to(ROOT)),bytes=size,sha256=hashlib.sha256(data).hexdigest(),symlink=f.is_symlink()));total+=size;count+=1
 entries.append(dict(path=str(root.relative_to(ROOT)),directory=root.is_dir(),reason=roots[root],files=records))
manifest=dict(status='reviewed_not_yet_deleted',scope='Only inspected project-generated and obsolete artifacts; source/config/tests/final documents/useful evidence retained',files=count,bytes=total,markdown_policy='README.md is the sole retained Markdown; previous content consolidated and outdated claims superseded',database_review='See database-inventory.json; paths are synthetic/demo fixtures; no running project services or operational data',entries=entries)
file=OUT/'cleanup-manifest.json';file.write_text(json.dumps(manifest,indent=2))
print(json.dumps(dict(candidates=len(entries),files=count,bytes=total,apply=args.apply),indent=2))
if args.apply:
 for entry in entries:
  target=ROOT/entry['path'];assert target.resolve().is_relative_to(ROOT)
  if target.is_dir():shutil.rmtree(target)
  else:target.unlink()
 for directory in sorted(ROOT.rglob('*'),key=lambda p:len(p.parts),reverse=True):
  if directory.is_dir() and not any(directory.iterdir()):directory.rmdir()
 manifest['status']='deleted_after_review';manifest['remaining_markdown']=[str(p.relative_to(ROOT)) for p in ROOT.rglob('*.md')];assert manifest['remaining_markdown']==['README.md'];file.write_text(json.dumps(manifest,indent=2));print('Cleanup applied; one Markdown retained.')
