import importlib
from pathlib import Path


def resolve_package_path(submodule: str) -> Path:
    """retrieve path inside submodule

    Args:
        submodule (str): submodule (e.i package.submodule.level)

    Returns:
        Path: absolute path of submodule
    """

    levels = submodule.split(".")

    package = importlib.import_module(levels[0])
    package_path = package.__path__[0]

    submodule_path = "/".join(levels[1:])
    submodule_path = submodule_path.replace("-", "_")

    return Path(f"{package_path}/{submodule_path}")
