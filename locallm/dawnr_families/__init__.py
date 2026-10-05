"""The families of locallm/dawnr_factory.py, a module a group. Importing this package registers them all; a module
that does not import is named on stderr and left out, so that one group's mistake does not take the rest with it."""
import importlib
import pkgutil
import sys

BROKEN: dict = {}
for _module in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
    try:
        importlib.import_module(f"{__name__}.{_module.name}")
    except Exception as error:                                  # noqa: BLE001
        BROKEN[_module.name] = f"{type(error).__name__}: {error}"
        print(f"dawnr_families: {_module.name} did not import ({BROKEN[_module.name]})", file=sys.stderr)
