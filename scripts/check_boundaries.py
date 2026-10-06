"""Repository boundary checks: no engine imports, vendored data, fonts or caches."""
import ast
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT/'src/xsr').rglob('*.py'):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or '']
        else:
            continue
        assert not any(name.split('.')[0].lower() in ('kage','hieropy') for name in names), path
tracked = subprocess.check_output(['git','ls-files','-z'], cwd=ROOT).decode().split('\0')
for name in tracked:
    path = Path(name)
    assert path.suffix.lower() not in ('.ttf','.otf','.woff','.woff2','.kage','.dump'), name
    assert not any(part.lower() in ('glyphwiki','kage','node_modules','.xsr-cache') for part in path.parts), name
print('Repository boundary verified: no external engine imports or tracked engine/data/font/cache paths')
