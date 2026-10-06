"""Sanity-check the committed or rebuilt four- or five-page Khitan PDF."""
import argparse
from pathlib import Path
import fitz


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    args = parser.parse_args()
    with fitz.open(args.pdf) as pdf:
        assert len(pdf) in (4, 5), f'expected four or five pages, found {len(pdf)}'
        for index, page in enumerate(pdf):
            assert 'XSR 0.10 | Khitan Small Script' in page.get_text(), index
            assert page.get_fonts(), f'no embedded fonts on page {index+1}'
            pix = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            assert sum(value < 100 for value in pix.samples) > 1000, index
        assert 'Noto native' in pdf[3].get_text()
        if len(pdf) == 5:
            assert 'Noto vs Khitan Small Linear' in pdf[4].get_text()
        print(f'{args.pdf}: {len(pdf)} nonblank pages, native comparison included')


if __name__ == '__main__':
    main()
