"""Download the reference font from official Noto sources; never vendor it."""
import argparse
import hashlib
from pathlib import Path
from urllib.request import urlopen

URL = 'https://raw.githubusercontent.com/notofonts/noto-fonts/main/hinted/ttf/NotoSansEgyptianHieroglyphs/NotoSansEgyptianHieroglyphs-Regular.ttf'
SHA256 = '04108b2f009bcb917df82f6aa59eea4baf02af28cd5f07e7fffb6c162454c87b'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('tmp/fonts/NotoSansEgyptianHieroglyphs-Regular.ttf'))
    args=parser.parse_args()
    with urlopen(URL, timeout=60) as response:
        data=response.read()
    actual=hashlib.sha256(data).hexdigest()
    if actual!=SHA256:
        raise SystemExit(f'Noto checksum mismatch: expected {SHA256}, got {actual}')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(data)
    print(args.output)

if __name__=='__main__':
    main()
