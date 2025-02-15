from collections import UserList

from aymurai.datasets.ar_juz_pcyf_10.labelstudio.utils import load_annotations


class ArgentinaJuzgadoPCyF10LabelStudioAnnotations(UserList):
    def __init__(self, basepath: str):
        self.data = load_annotations(basepath)
