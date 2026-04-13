from .config import DataAugmentationRunConfig, load_data_augmentation_config

__all__ = [
    "DataAugmentationRunConfig",
    "DataAugmenter",
    "load_data_augmentation_config",
]


def __getattr__(name: str):
    if name == "DataAugmenter":
        from .core import DataAugmenter

        return DataAugmenter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
