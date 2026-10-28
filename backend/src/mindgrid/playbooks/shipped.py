"""Specs that ship with the code: the built-ins here and each pack's, found through the
`mindgrid.playbooks` entry point group (each entry names a package holding *.json specs).
Packs never import this layer: they only ship files."""

import functools
from importlib.metadata import entry_points
from importlib.resources import files

from .spec import PlaybookSpec

BUILTIN_PACKAGE = "mindgrid.playbooks.builtin"


def _from_package(package: str) -> list[PlaybookSpec]:
    folder = files(package)
    return [
        PlaybookSpec.model_validate_json(item.read_bytes())
        for item in sorted(folder.iterdir(), key=lambda f: f.name)
        if item.name.endswith(".json")
    ]


@functools.cache
def all_specs() -> dict[tuple[str, int], PlaybookSpec]:
    packages = [BUILTIN_PACKAGE, *(e.value for e in entry_points(group="mindgrid.playbooks"))]
    found: dict[tuple[str, int], PlaybookSpec] = {}
    for package in packages:
        for spec in _from_package(package):
            key = (spec.id, spec.version)
            if key in found:
                raise ValueError(f"playbook {spec.id} v{spec.version} is shipped twice")
            found[key] = spec
    return found
