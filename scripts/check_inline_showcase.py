"""Verify four nonblank pages with image and vector glyphs."""
import argparse
import fitz


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf');args=parser.parse_args()
    with fitz.open(args.pdf) as pdf:
        assert len(pdf)==4
        for index,page in enumerate(pdf):
            assert 'XSR 0.10 / Inline glyphs' in page.get_text(),index
            assert page.get_images(),index
            assert page.get_drawings(),index
            assert sum(v<100 for v in page.get_pixmap().samples)>1000,index
        assert len(pdf[1].get_images())>=5
    print(f'{args.pdf}: 4 nonblank pages; raster and vector payloads preserved')


if __name__=='__main__':
    main()
