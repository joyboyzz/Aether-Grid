from pathlib import Path
import pymupdf as fitz
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'verification/final/document-qa';DEST.mkdir(parents=True,exist_ok=True)
for kind,file in [('deck','AetherGrid_Pitch_Deck_Praveen_Sudireddy.pdf'),('paper','AetherGrid_Paper_Praveen_Sudireddy.pdf')]:
    doc=fitz.open(ROOT/'paper'/file)
    for i,page in enumerate(doc):page.get_pixmap().save(DEST/f'{kind}-{i+1:02}.png')
    for group in range((len(doc)+5)//6):
        cellheight=390 if kind=='deck' else 580
        sheet=Image.new('RGB',(1200,3*cellheight),'#d4dde6');draw=ImageDraw.Draw(sheet)
        for j in range(6):
            k=group*6+j
            if k>=len(doc):break
            im=Image.open(DEST/f'{kind}-{k+1:02}.png');im.thumbnail((580,cellheight-40))
            x=(j%2)*600+10;y=(j//2)*cellheight+24;sheet.paste(im,(x,y));draw.text((x,y-18),f'{kind} {k+1}',fill='black')
        sheet.save(DEST/f'{kind}-sheet-{group+1}.jpg')
