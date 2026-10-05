"""Fetch the official, revision-pinned Noto Serif Khitan Small Script font."""
import argparse
import hashlib
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile
from io import BytesIO

# Official notofonts/khitan-small-script release, commit
# c659d517071caaa442218626c6b59db52c785c76.
URL = ('https://github.com/notofonts/khitan-small-script/releases/download/'
       'NotoSerifKhitanSmallScript-v1.000/NotoSerifKhitanSmallScript-v1.000.zip')
ARCHIVE_SHA256 = 'daf885a451fe4c9446d5cbbe6c8a2415b62d92f2636cbd1bacb29da4d7475ff5'
MEMBER = ('NotoSerifKhitanSmallScript/hinted/ttf/'
          'NotoSerifKhitanSmallScript-Regular.ttf')
FONT_SHA256 = 'ad6d20d17e7b0af746106b8e0e3ac65c47f6813a4acb6e05786023e1374a953f'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path('tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf'))
    args = parser.parse_args()
    archive = urlopen(URL, timeout=60).read()
    actual = hashlib.sha256(archive).hexdigest()
    if actual != ARCHIVE_SHA256:
        raise SystemExit(f'Noto archive checksum mismatch: {actual}')
    with ZipFile(BytesIO(archive)) as package:
        font = package.read(MEMBER)
    actual = hashlib.sha256(font).hexdigest()
    if actual != FONT_SHA256:
        raise SystemExit(f'Noto font checksum mismatch: {actual}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(font)
    print(args.output)


if __name__ == '__main__':
    main()