'''Unicode-driven stack rendering framework for XeTeX.'''

from importlib.metadata import version as _distribution_version

from .registry import Registry

__all__ = ['Registry', 'build_default_registry']
__version__ = _distribution_version('xetex-stack-renderer')


def build_default_registry() -> Registry:
    '''Build the registry shipped with this release.'''
    from .egyptian import register_script
    from .khitan import register_script as register_khitan

    registry = Registry()
    register_script(registry)
    register_khitan(registry)
    return registry
