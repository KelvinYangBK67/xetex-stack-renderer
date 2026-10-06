"""Original neutral glyph fixtures. Creation only; no user-image processing."""
from pathlib import Path
from PIL import Image, ImageDraw


def make_asset(path, width=120, height=120):
    path=Path(path)
    points=[(.2,.2,.8,.2),(.3,.2,.3,.8),(.3,.8,.8,.65),(.7,.35,.7,.8)]
    if path.suffix=='.svg':
        d=' '.join(f'M{x*width} {y*height}L{a*width} {b*height}' for x,y,a,b in points)
        path.write_text(f'<svg viewBox="0 0 {width} {height}"><path d="{d}" fill="none" stroke="black" stroke-width="{min(width,height)*.06}"/></svg>', encoding='utf-8')
    elif path.suffix=='.pdf':
        import fitz
        doc=fitz.open();page=doc.new_page(width=width,height=height)
        for x,y,a,b in points:
            page.draw_line((x*width,y*height),(a*width,b*height),color=(0,0,0),width=min(width,height)*.06)
        doc.save(path);doc.close()
    else:
        image=Image.new('RGB',(width,height),'white')
        draw=ImageDraw.Draw(image)
        for x,y,a,b in points:
            draw.line((x*width,y*height,a*width,b*height),fill='black',width=max(1,round(min(width,height)*.06)))
        image.save(path)
    return path
