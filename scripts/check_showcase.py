"""Automated PDF sanity checks supplement (not replace) visual review."""
import argparse
from pathlib import Path
import fitz


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf',type=Path)
    args=parser.parse_args()
    with fitz.open(args.pdf) as pdf:
        assert len(pdf)==6, f'expected six pages, found {len(pdf)}'
        fonts=set()
        for index,page in enumerate(pdf):
            assert 'XSR 0.10' in page.get_text(),f'missing heading on page {index+1}'
            for xref,ext,typ,name,*_ in page.get_fonts():
                if ext=='ttf':
                    fonts.add(name)
                    assert pdf.extract_font(xref)[3],f'font {name} is not embedded'
            pix=page.get_pixmap(matrix=fitz.Matrix(1,1),alpha=False)
            assert sum(value<100 for value in pix.samples)>1000, f'blank page {index+1}'
        assert len(fonts)>=2,f'expected at least two embedded reference fonts, found {fonts}'
    print(f'{args.pdf}: 6 nonblank pages, {len(fonts)} embedded reference fonts')

if __name__=='__main__':
    main()
