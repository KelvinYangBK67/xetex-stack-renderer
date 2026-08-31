'''Unicode-driven stack rendering framework for XeTeX.'''

from .registry import Registry

__all__ = ['Registry', 'build_default_registry']
__version__ = '0.2.0'


def build_default_registry() -> Registry:
    '''Build the registry shipped with this release.'''
    from .egyptian import register_script

    registry = Registry()
    register_script(registry)
    return registry
