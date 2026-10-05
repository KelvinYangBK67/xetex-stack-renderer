"""Download the checksum-pinned official NewGardiner reference font for tests.

The font remains external to XSR's runtime package and wheel. License: SIL OFL 1.1.
"""
import argparse
import hashlib
from pathlib import Path
from urllib.request import urlopen

REVISION = 'e9334aaff65e0543a4b5d3a362fb5262043b2dd5'
URL = f'https://raw.githubusercontent.com/nederhof/newgardiner/{REVISION}/fonts/NewGardiner.ttf'
SHA256 = '3c7710d6f7bb8cf791699c08f0cc453de5a9b6a12278ce3d727129163259f79d'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('tmp/fonts/NewGardiner.ttf'))
    args = parser.parse_args()
    with urlopen(URL,timeout=60) as response:
        data = response.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != SHA256:
        raise SystemExit(f'NewGardiner checksum mismatch: expected {SHA256}, got {actual}')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(data)
    print(args.output)

if __name__ == '__main__':
    main()
