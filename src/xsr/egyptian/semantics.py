"""Egyptian Unicode constraints, independent of parser and font geometry."""
from ..errors import XSRError
from .unicode_data import ROTATIONS, NO_MIRROR, NO_ROTATE


def rotation(base, selector):
    if not selector:
        return 0
    pair = (base, 0xFE00 + selector - 1)
    if pair in ROTATIONS:
        # Specific registered variants take precedence over the broad NoRotate
        # property (Unicode lists both for e.g. M003 and V006).
        return ROTATIONS[pair]
    code = 'XSR-NO-ROTATE' if base in NO_ROTATE else 'XSR-VARIANT-UNREGISTERED'
    raise XSRError(code, f'U+{base:05X} U+{pair[1]:04X} is not a permitted standardized rotation')


def validate_mirror(base, mirror):
    if mirror and base in NO_MIRROR:
        raise XSRError('XSR-NO-MIRROR', f'U+{base:05X} cannot take U+13440; use the separately encoded sign')


def layout_options(options):
    direction = options.get('direction', 'ltr')
    mode = options.get('writing_mode', 'horizontal')
    if mode != 'horizontal':
        raise XSRError('XSR-WRITING-MODE-UNSUPPORTED', f'writing_mode={mode}; only horizontal text flow is implemented')
    if direction not in ('ltr', 'rtl'):
        raise XSRError('XSR-DIRECTION', f'unknown Egyptian direction {direction!r}; use ltr or rtl')
    return direction
