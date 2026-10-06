"""Check nonblank vector-only illustrations on all three showcase pages."""
import argparse
import fitz


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf')
    args = parser.parse_args()
    with fitz.open(args.pdf) as pdf:
        assert len(pdf) == 3
        for index, page in enumerate(pdf):
            assert 'XSR 0.10' in page.get_text(), index
            assert len(page.get_drawings()) >= 3, index
            assert not page.get_images(), 'raster image in vector showcase'
            pix = page.get_pixmap()
            assert sum(v < 100 for v in pix.samples) > 1000
    print(f'{args.pdf}: 3 nonblank pages with vector illustrations; no images')


if __name__ == '__main__':
    main()
