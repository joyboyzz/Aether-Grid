"""Reproducible typography/vector GitHub visuals. No invented live metrics or company claims."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];O=R/'assets/github';O.mkdir(parents=True,exist_ok=True)
FONT=Path('/usr/share/fonts/truetype/dejavu');BG='#08141e';PANEL='#102732';FG='#edf5f3';MUTED='#9bafb9';GREEN='#c1f16e';CYAN='#62d4c8';EDGE='#25404c'
def font(n,b=False,mono=False):return ImageFont.truetype(str(FONT/('DejaVuSansMono.ttf' if mono else 'DejaVuSans-Bold.ttf' if b else 'DejaVuSans.ttf')),n)
def text(d,p,s,size=24,b=False,color=FG,mono=False):d.text(p,s,font=font(size,b,mono),fill=color,spacing=8)
def panel(d,box,fill=PANEL,r=20,outline=EDGE):d.rounded_rectangle(box,r,fill=fill,outline=outline,width=2)
def grid(d,w,h):
 for x in range(30,w,50):
  for y in range(30,h,50):d.ellipse((x,y,x+1,y+1),fill='#1a303b')
def brand(d,x,y,size=34):
 d.rounded_rectangle((x,y+5,x+12,y+size+7),5,fill=GREEN);text(d,(x+29,y),'AETHERGRID',size,True)
def flow(d,x,y,scale=1):
 # All nodes are architecture labels, not a live delivery route.
 def n(yy,title,sub,accent=False):
  panel(d,(x,y+yy,x+420*scale,y+yy+88*scale),GREEN if accent else PANEL,18)
  text(d,(x+20*scale,y+yy+12*scale),title,round(22*scale),True,BG if accent else FG)
  text(d,(x+20*scale,y+yy+49*scale),sub,round(15*scale),False,'#274238' if accent else MUTED)
 n(0,'01  TELEMETRY','Software HMAC + replay checks')
 n(111*scale,'02  QUALIFY','Heuristic life + buyer eligibility')
 n(222*scale,'03  HUMAN REVIEW','Separate operator confirmation',True)
 n(333*scale,'04  RECORD','Simulated ledger + reported receipt')
 for yy in [88,199,310]:
  d.line((x+210*scale,y+yy*scale,x+210*scale,y+(yy+23)*scale),fill=CYAN,width=3)
def cover(w,h,out):
 im=Image.new('RGB',(w,h),BG);d=ImageDraw.Draw(im);grid(d,w,h)
 if w==1280:
  brand(d,58,40,34);text(d,(60,108),'INDEPENDENT PERSONAL PROJECT',17,False,CYAN,True)
  text(d,(53,167),'Beyond\nthe alert.',81,True)
  text(d,(60,385),'Cold-chain software.\nReviewed decisions. Honest boundaries.',23,False,FG)
  flow(d,790,78,.91)
  d.line((60,502,w-60,502),fill=EDGE,width=2)
  text(d,(60,526),'Praveen Sudireddy',27,True);text(d,(60,567),'Digital Specialist Engineer (DSE), Infosys',18,False,MUTED)
  text(d,(796,530),'SIMULATED OUTCOMES',17,False,CYAN,True);text(d,(796,564),'Author role only; no endorsement',14,False,MUTED)
 else:
  brand(d,70,50,42);text(d,(72,127),'INDEPENDENT PERSONAL ENGINEERING PROJECT',20,False,CYAN,True)
  text(d,(62,193),'Beyond the alert.',83,True)
  text(d,(72,321),'Signed telemetry. Qualified buyers.\nHuman-reviewed decisions. A simulated ledger.',29,False,FG)
  chips=['ASP.NET CORE 10','REACT + TYPESCRIPT','PYTHON REFERENCE','SQLITE + SSE'];x=72
  for label in chips:
   width=int(d.textlength(label,font=font(15,mono=True)))+32;panel(d,(x,450,x+width,495),PANEL,22);text(d,(x+16,462),label,15,False,CYAN,True);x+=width+12
  flow(d,1100,80,.97)
  d.line((72,567,w-72,567),fill=EDGE,width=2)
  text(d,(72,590),'Praveen Sudireddy',29,True);text(d,(72,636),'Digital Specialist Engineer (DSE), Infosys',21,False,MUTED)
  text(d,(987,600),'SOFTWARE PROTOTYPE',18,False,GREEN,True);text(d,(987,639),'No real payments · Hardware excluded',16,False,MUTED)
 im.save(O/out,optimize=True)
cover(1280,640,'social-preview.png');cover(1600,720,'readme-hero.png')
# Readable architecture schematic.
im=Image.new('RGB',(1600,980),BG);d=ImageDraw.Draw(im);grid(d,1600,980)
text(d,(65,50),'ONE WORKFLOW. FIVE CLEAR LAYERS.',40,True);text(d,(65,115),'Native software architecture · provider boundary, not fabricated hardware',23,False,MUTED)
rows=[('L4','PORTALS','Command · Buyer · Analytics · Carrier · Insurance'),('L3','WORKFLOW','Reservations → operator review → simulated settlement → receipt'),('L2','DETERMINISTIC MODELS','BioTimer · thermal Dijkstra · eligibility · settlement arithmetic'),('L1','INTEGRITY + IDENTITY','Software HMAC v2 · bindings · freshness · persisted replay cursor'),('L0','TELEMETRY PROVIDER','Software packets / local simulation · hardware fabrication excluded')]
for i,(idx,title,body) in enumerate(rows):
 y=192+i*132;panel(d,(65,y,1535,y+110),PANEL,18)
 text(d,(90,y+27),idx,32,True,GREEN);text(d,(193,y+16),title,25,True);text(d,(193,y+61),body,23,False,MUTED)
 if i<4:d.line((800,y+111,800,y+131),fill=CYAN,width=3)
text(d,(65,887),'SQLite WAL + atomic document/outbox commits     |     HTTP ingest + SSE replay',21,False,CYAN)
im.save(O/'architecture.png',optimize=True)
# Proof strip, always qualified as local recorded evidence.
im=Image.new('RGB',(1600,340),BG);d=ImageDraw.Draw(im)
for i,(n,label,sub) in enumerate([('51','PYTHON TESTS','Regression suite'),('2,230','PARITY ASSERTIONS','Calculation fixtures'),('70','ROUTING CASES','Seven profiles'),('2,100','FIELD COMPARISONS','Ranked route output')]):
 x=20+i*398;panel(d,(x,24,x+377,249),PANEL,20);text(d,(x+24,49),n,57,True,GREEN);text(d,(x+24,139),label,20,True);text(d,(x+24,185),sub,19,False,MUTED)
text(d,(44,286),'Recorded local software evidence — not a live CI badge, physical-rescue rate or production certification.',22,False,MUTED)
im.save(O/'verification-strip.png',optimize=True)
# Cropped real acceptance UI with visible simulation banner, never relabelled as a live system.
shot=Image.open(R/'verification/final/journey-operator-settled.png').convert('RGB');shot=shot.crop((0,0,shot.width,850));shot.thumbnail((1450,850))
im=Image.new('RGB',(1600,1220),BG);d=ImageDraw.Draw(im);text(d,(65,42),'ACTUAL UI. SYNTHETIC ACCEPTANCE RUN.',33,True);text(d,(65,104),'Separate buyer/operator accounts completed the reviewed browser flow.',24,False,MUTED)
im.paste(shot,(75,180));d.line((65,180+shot.height+24,1535,180+shot.height+24),fill=EDGE,width=2)
text(d,(75,180+shot.height+52),'₹1,08,780 simulated credit · 90.65% of the stated ₹1,20,000 test baseline',27,True,CYAN)
text(d,(75,180+shot.height+105),'No real payment or independently verified physical receipt.',22,False,MUTED)
im.save(O/'product-preview.png',optimize=True)
print('Created social cover, README hero, architecture, evidence strip and actual-UI preview.')
