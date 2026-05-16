# Runtime hook – fix shibokensupport / six incompatibility in frozen bundles.
#
# Root cause:
#   shibokensupport.feature._mod_uses_pyside() calls inspect.getsource()
#   on every imported module to detect PySide usage.  For modules created
#   by six's _SixMetaPathImporter (e.g. six.moves._thread), inspect.getfile()
#   internally calls _module_repr() which crashes with:
#       AttributeError: '_SixMetaPathImporter' object has no attribute '_path'
#   _mod_uses_pyside catches TypeError / OSError / SyntaxError but NOT
#   AttributeError, so the exception propagates and kills the process.
#
# Fix:
#   Wrap inspect.getfile so that any AttributeError from a module loader that
#   lacks source-location metadata is converted to TypeError.  This is
#   semantically correct: TypeError is the standard signal that an object
#   has no associated source file (used e.g. for built-in modules).
#   After the conversion, _mod_uses_pyside catches TypeError and returns
#   False cleanly, treating the module as "not using PySide".

import inspect as _inspect

_orig_getfile = _inspect.getfile


def _safe_getfile(object):
    try:
        return _orig_getfile(object)
    except AttributeError as exc:
        # NB: must NOT use repr(object) here – on the offending module repr()
        # itself triggers _module_repr_from_spec, which re-raises the same
        # AttributeError on _SixMetaPathImporter._path and defeats the fix.
        name = getattr(object, "__name__", "<unknown>")
        raise TypeError(
            f"module {name!r} has no source file (virtual loader)"
        ) from exc


_inspect.getfile = _safe_getfile
