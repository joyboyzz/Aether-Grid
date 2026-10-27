"""LinkedIn portrait document carousel; factual copy + actual synthetic acceptance screenshot."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from PIL import Image
import pymupdf as fitz,json,zipfile
R=Path(__file__).resolve().parents[1];OUT=R/'linkedin';OUT.mkdir(exist_ok=True)
for name,file in [('S','DejaVuSans.ttf'),('B','DejaVuSans-Bold.ttf'),('M','DejaVuSansMono.ttf')]:pdfmetrics.registerFont(TTFont(name,'/usr/share/fonts/truetype/dejavu/'+file))
W,H=1080,1350;BG='#07131D';FG='#EFF6F4';MUTED='#9AAFB9';GREEN='#C4F46E';CYAN='#68D9CE';LINE='#213641';PANEL='#10232D'
pdf=OUT/'AetherGrid_LinkedIn_Carousel.pdf';c=canvas.Canvas(str(pdf),pagesize=(W,H));c.setTitle('AetherGrid — Beyond the Alert');c.setAuthor('Praveen Sudireddy | Digital Specialist Engineer (DSE), Infosys')
def rect(x,y,w,h,color,r=0,stroke=None):
 c.setFillColor(HexColor(color));c.setStrokeColor(HexColor(stroke or color));c.roundRect(x,H-y-h,w,h,r,fill=1,stroke=bool(stroke))
def line(x,y,x2,y2,color=LINE,width=2):
 c.setStrokeColor(HexColor(color));c.setLineWidth(width);c.line(x,H-y,x2,H-y2)
def text(s,x,y,size=32,font='S',color=FG,leading=None):
 for i,v in enumerate(s.split('\n')):
  assert pdfmetrics.stringWidth(v,font,size)<=W-x-48,(s,size)
  c.setFillColor(HexColor(color));c.setFont(font,size);c.drawString(x,H-y-size*.83-i*(leading or size*1.15),v)
def wrap(s,x,y,width,size=28,font='S',color=MUTED,leading=None):
 out=[];row=''
 for w in s.split():
  trial=(row+' '+w).strip()
  if pdfmetrics.stringWidth(trial,font,size)>width:out.append(row);row=w
  else:row=trial
 if row:out.append(row)
 text('\n'.join(out),x,y,size,font,color,leading);return y+len(out)*(leading or size*1.15)
def base(n,section):
 rect(0,0,W,H,BG)
 for x in range(60,1080,80):
  for y in range(88,1200,80):rect(x,y,2,2,'#142B35')
 rect(60,54,12,32,GREEN,4);text('AETHERGRID',87,55,28,'B');text(f'{n:02d} / 06',874,61,19,'M',MUTED)
 line(60,111,1020,111);text(section.upper(),60,141,18,'M',CYAN)
 line(60,1225,1020,1225)
 text('PRAVEEN SUDIREDDY',60,1250,20,'B')
 text('Digital Specialist Engineer (DSE), Infosys',60,1283,17,'S',MUTED)
 text('INDEPENDENT PERSONAL PROJECT',60,1314,12,'M',MUTED)
 text('AUTHOR ROLE ONLY · NO EMPLOYER ENDORSEMENT',624,1314,12,'S',MUTED)
def badge(s,x,y,w):rect(x,y,w,44,PANEL,22,LINE);text(s,x+18,y+13,16,'M',CYAN)
# 01 / Hook
base(1,'Beyond the alert')
text('THE ALERT',54,226,106,'B',FG)
text('IS ONLY',54,345,106,'B',FG)
text('STEP ONE.',54,464,106,'B',GREEN)
wrap('What happens after a cold-chain temperature warning?',62,638,875,36,'S',FG,49)
# Compact route motif, not a claimed live route.
points=[(83,878),(297,878),(512,821),(727,878),(984,878)]
for a,b in zip(points,points[1:]):line(*a,*b,CYAN,4)
for i,(x,y) in enumerate(points):rect(x-9,y-9,18,18,GREEN if i in [0,4] else CYAN,9)
text('DETECT',60,923,15,'M',MUTED);text('QUALIFY',260,923,15,'M',MUTED);text('REVIEW',690,923,15,'M',MUTED);text('RECORD',935,923,15,'M',MUTED)
wrap('I built a software prototype to explore the decisions after detection.',60,1000,930,30,'S',FG,42)
badge('SOFTWARE-ONLY',60,1120,213);badge('SIMULATED OUTCOMES',289,1120,304);badge('SWIPE TO EXPLORE →',610,1120,353)
c.showPage()
# 02 / System
base(2,'The reviewed workflow')
text('From a reading\nto a reviewed\ndecision.',60,212,76,'B',FG,86)
steps=[('01','Signed telemetry','Software HMAC + identity / replay checks'),('02','Heuristic distress','Exposure model, not a food-safety verdict'),('03','Buyer qualification','Full lot · capacity · funds · reachability'),('04','Reservation','Simulated resources held; no settlement yet'),('05','Operator confirmation','A separate authorized reviewer must decide'),('06','Ledger + reported receipt','Simulation recorded; receipt is an assertion')]
for i,(num,title,sub) in enumerate(steps):
 y=528+i*105
 if i<5:line(85,y+37,85,y+106,LINE,3)
 rect(60,y,50,50,GREEN if i==4 else PANEL,12)
 text(num,70,y+15,18,'M',BG if i==4 else CYAN)
 text(title,137,y+1,28,'B',GREEN if i==4 else FG)
 text(sub,137,y+44,20,'S',MUTED)
text('Automatic initiation ≠ automatic final settlement.',60,1175,23,'B',CYAN)
c.showPage()
# 03 / Actual UI proof
base(3,'Actual acceptance-run screenshot')
text('Real screens.\nSynthetic outcomes.',60,212,71,'B',FG,86)
wrap('Separate buyer and operator browsers completed the reviewed flow.',60,412,930,29,'S',MUTED,40)
im=Image.open(R/'verification/final/journey-operator-settled.png').convert('RGB');im=im.crop((0,0,im.width,720))
rect(55,535,970,490,LINE,12);c.drawImage(ImageReader(im),60,H-540-480,960,480)
text('CROPPED FROM THE ACTUAL LOCAL SYNTHETIC TEST',60,1044,15,'M',MUTED)
rect(60,1090,470,98,PANEL,14);text('₹1,08,780',80,1105,42,'B',GREEN);text('SIMULATED FARMER CREDIT',80,1160,14,'M',MUTED)
rect(548,1090,472,98,PANEL,14);text('90.65%',568,1105,42,'B',CYAN);text('OF THE ₹1,20,000 TEST BASELINE',568,1160,14,'M',MUTED)
c.showPage()
# 04 / Evidence
base(4,'Evidence, not inflated claims')
text('Less “it works.”\nMore “here’s\nwhat I checked.”',60,210,68,'B',FG,81)
for y,num,label,detail in [(513,'51','PYTHON TESTS','Regression suite: no failures or errors'),(697,'2,230','CALCULATION ASSERTIONS','Python / .NET reference parity'),(881,'70','ROUTING CASES','7 profiles · 2,100 field comparisons')]:
 rect(60,y,960,159,PANEL,16);text(num,84,y+27,66,'B',GREEN);text(label,425,y+32,22,'B',FG);wrap(detail,425,y+81,565,22,'S',MUTED,31)
wrap('Also checked: five portals, role isolation, duplicate guards and forced-crash recovery.',60,1081,920,27,'S',FG,37)
text('Software evidence. Not physical-rescue evidence.',60,1178,22,'B',CYAN)
c.showPage()
# 05 / Lesson
base(5,'The most useful bug')
text('My best result\nwasn’t a\ngreen tick.',60,211,80,'B',FG,92)
rect(60,551,960,218,PANEL,18)
text('WHAT THE FIRST TESTS MISSED',85,581,19,'M',CYAN)
wrap('Operator-only smoke tests did not catch a buyer-role portal/API access mismatch.',85,632,875,32,'B',FG,44)
rect(60,803,960,257,PANEL,18)
text('WHAT CHANGED',85,833,19,'M',GREEN)
wrap('Fixed buyer-scoped access. Then tested the full browser journey with separate buyer and operator accounts.',85,883,873,31,'S',FG,44)
wrap('A passing admin dashboard is not proof that every user journey works.',60,1110,930,28,'B',CYAN,38)
c.showPage()
# 06 / Scope + CTA
base(6,'Built in public. Boundaries included.')
text('Built to learn.\nDesigned to\nshow its limits.',60,212,77,'B',FG,88)
text('TESTED IN SOFTWARE',60,549,19,'M',GREEN)
for i,s in enumerate(['Reviewed end-to-end simulation','Scoped access + recovery controls','Deterministic reference parity']):text('→ '+s,60,596+i*51,28,'S',FG)
line(60,773,1020,773)
text('NOT CLAIMED',60,815,19,'M',CYAN)
for i,s in enumerate(['Real payments or verified physical rescue','Field-validated shelf-life accuracy','Production deployment certification']):text('— '+s,60,863+i*49,27,'S',MUTED)
text('Hardware fabrication is excluded.',60,1038,25,'S',FG)
text('What would you test next?',60,1125,39,'B',GREEN)
c.showPage();c.save()
# Export posting-ready 4:5 PNGs, without adding more Markdown documents.
doc=fitz.open(pdf)
for i,page in enumerate(doc):page.get_pixmap(alpha=False).save(OUT/f'AetherGrid_Slide_{i+1:02d}.png')
(OUT/'AetherGrid_Cover.png').write_bytes((OUT/'AetherGrid_Slide_01.png').read_bytes())
qa=[]
for i,page in enumerate(doc):
 for x0,y0,x1,y1,word,*_ in page.get_text('words'):
  if min(x0,y0)<0 or x1>W+.5 or y1>H+.5:qa.append(dict(page=i+1,word=word))
assert len(doc)==6 and not qa,qa
(OUT/'media_checks.json').write_text(json.dumps(dict(pages=6,pixels=[W,H],text_bounds_issues=qa,uses_actual_screenshot=True,screenshot_source='verification/final/journey-operator-settled.png',independent_project=True,simulated_outcomes_labelled=True),indent=2))
print('Created 6-page PDF carousel and 1080×1350 PNG media.')
