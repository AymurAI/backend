import sys
import logging
from collections import UserDict

import datasets
import pandas as pd

from aymurai.datasets.ar_juz_pcyf_10.common import VALIDATION_FIELDS

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


class ArgentinaJuzgadoPCyF10ValidationFields(UserDict):
    """Criminal Court 10 PCyF, Ciudad Autonoma de Buenos Aires, Argentina OpenCourt dataset."""

    def __init__(self):

        dl_manager = datasets.DownloadManager()

        vals_path = dl_manager.download(VALIDATION_FIELDS)
        vals = pd.read_csv(vals_path)
        vals.columns = [col.lower().strip() for col in vals.columns]
        vals.dropna(axis=1, how="all", inplace=True)

        arts = vals[
            ["art_infringido", "codigo_o_ley", "conducta", "conducta_descripcion"]
        ]
        arts.dropna(axis=1, how="all", inplace=True)
        arts = arts.to_dict(orient="list")

        vals = vals.to_dict(orient="list")
        vals = {
            k: list(filter(lambda x: not pd.isna(x), set(v))) for k, v in vals.items()
        }
        vals["article_group"] = arts
        self.data = vals

        return
