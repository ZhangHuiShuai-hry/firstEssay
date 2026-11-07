"""Render the manuscript for visual QA using PyMuPDF and Pillow."""
from pathlib import Path
import math
import pymupdf
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parents[1]
OUT=HERE/'qa/revision2';OUT.mkdir(parents=True,exist_ok=True)
for name,short in [('HCDP','main'),('HCDP_SF','supp')]:
    doc=pymupdf.open(HERE/(name+'.pdf'));tiles=[]
    for i,p in enumerate(doc):
        path=OUT/f'{short}_{i+1:02}.png'
        p.get_pixmap(matrix=pymupdf.Matrix(1.4,1.4)).save(path)
        im=Image.open(path).convert('RGB');im.thumbnail((306,396))
        tile=Image.new('RGB',(326,426),'#ddd');tile.paste(im,((326-im.width)//2,14))
        ImageDraw.Draw(tile).text((12,408),f'{short} {i+1}',fill='black');tiles.append(tile)
    cols=min(4,len(tiles));rows=math.ceil(len(tiles)/cols)
    sheet=Image.new('RGB',(326*cols,426*rows),'white')
    for i,tile in enumerate(tiles):sheet.paste(tile,((i%cols)*326,(i//cols)*426))
    sheet.save(HERE/'qa'/f'review-{short}.png')
    print(name,'rendered',len(doc),'pages')
