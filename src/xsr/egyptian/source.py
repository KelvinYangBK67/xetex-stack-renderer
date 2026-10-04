"""Literal host-dispatch arguments in TeX sources; no macro expansion."""
import re
from ..registry import DetectedRun


def source_runs(source, registry):
    spans=[]
    for match in re.finditer(r'\\xsrEgyptianText\s*\{',source):
        start=match.end()
        depth=1
        end=start
        while end<len(source) and depth:
            if source[end]=='{':
                depth+=1
            elif source[end]=='}':
                depth-=1
            end+=1
        if depth:
            from ..errors import XSRError
            raise XSRError('XSR-PREPROCESS','unclosed literal xsrEgyptianText argument')
        spans.append((start,end-1))
    runs=[run for run in registry.script_runs(source)
          if not any(a<=run.start<b for a,b in spans)]
    runs.extend(DetectedRun('egyptian',source[a:b],a,b) for a,b in spans)
    return sorted(runs,key=lambda run:run.start)
