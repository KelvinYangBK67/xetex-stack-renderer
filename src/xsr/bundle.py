"""Atomic document-level response transport; bodies remain unevaluated TeX."""
import os
from pathlib import Path
import tempfile


def bundle_path(jobname):
    if not jobname or Path(jobname).name != jobname or jobname in ('.','..'):
        raise ValueError('jobname must be a single filename stem')
    return Path('.xsr') / f'{jobname}.responses.tex'


def atomic_text(path, text):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as stream:
            stream.write(text)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_bundle(output_dir, jobname, responses):
    relative=bundle_path(jobname)
    declarations=['% XSR-RESPONSES-1; generated, replace by preprocessing.\n']
    for digest,body in sorted(responses.items()):
        if len(digest)!=32 or any(c not in '0123456789ABCDEF' for c in digest):
            raise ValueError('invalid response digest')
        declarations.append(r'\xsrDeclareResponse{'+digest+'}{%\n'+body.rstrip()+'\n}%\n')
    atomic_text(Path(output_dir)/relative,''.join(declarations))
    return relative
