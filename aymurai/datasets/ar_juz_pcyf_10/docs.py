import os
import sys
import logging
from glob import iglob
from typing import Any, Union
from datetime import date, time
from collections import UserList

import pandas as pd

from aymurai.text.extraction import get_extension
from aymurai.datasets.ar_juz_pcyf_10.common import FIELDS
from aymurai.utils.cache import cache_load, cache_save, get_cache_key

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


class ArgentinaJuzgadoPCyF10DocsDataset(UserList):
    """Criminal Court 10 PCyF, Ciudad Autonoma de Buenos Aires, Argentina OpenCourt dataset."""

    @staticmethod
    def to_datetime(value):
        if isinstance(value, str):
            day, month, year = value.split("_")
            year_format = "%y" if len(year) == 2 else "%Y"
            if int(day) > 31 or int(month) > 12:
                return

            dtime = pd.to_datetime(
                value,
                format=f"%d_%m_{year_format}",
                infer_datetime_format=True,
                errors="coerce",
            )
            return dtime.strftime("%Y/%m/%d") if not pd.isna(dtime) else None

    def enforce_dtypes(self, df: pd.DataFrame, dtypes: dict[str, Any]) -> pd.DataFrame:
        for column, dtype in dtypes.items():
            if dtype == "date":
                df[column] = pd.to_datetime(df[column])
                df[column] = pd.Series(
                    [
                        date(year=v.year, month=v.month, day=v.day)
                        if not pd.isna(v)
                        else None
                        for v in df[column]
                    ]
                )
            elif dtype == "time":
                df[column] = pd.to_datetime(df[column])
                df[column] = pd.Series(
                    [
                        time(hour=int(v.hour), minute=int(v.minute))
                        if not pd.isna(v)
                        else None
                        for v in df[column]
                    ]
                )
            else:
                # fix of
                df[column] = df[column].astype(dtype)
        return df

    def __init__(self, use_cache: Union[str, bool] = True):
        DOCS_PATH = os.environ["AYMURAI_RESTRICTED_DOCUMENT_DOCS_PATH"]
        cache_overwrite = use_cache == "overwrite"

        cache_key = get_cache_key("private-docs", context="dataset-ar-juz-pcyf-10")
        if (
            use_cache
            and not cache_overwrite
            and (cache_data := cache_load(key=cache_key, logger=logger))
        ):
            logger.info("loading dataset from cache")
            self.data = cache_data
            return

        # documents are not matches with database so just return their paths
        paths = iglob(f"{DOCS_PATH}/**/*.*", recursive=True)
        paths = filter(os.path.isfile, paths)
        paths = list(sorted(paths))

        dataset = [
            {
                "path": path,
                "metadata": {
                    "extension": get_extension(path),
                },
            }
            for path in paths
        ]
        dataset = filter(
            lambda x: x["metadata"]["extension"].lower() in ["doc", "docx"],
            dataset,
        )
        dataset = list(dataset)
        self.data = dataset

        annotations_path = f"{DOCS_PATH}/base-docs.csv"
        annotations = pd.read_csv(annotations_path)

        annotations.columns = [col.lower().strip() for col in annotations.columns]

        # format dates
        annotations["date"] = annotations["fecha_resolucion"].apply(self.to_datetime)

        # reformat boolean/null categories
        annotations.replace("no_corresponde", None, inplace=True)
        annotations.replace("no corresponde", None, inplace=True)
        annotations.replace("s/d", None, inplace=True)
        annotations.replace("sin frases", None, inplace=True)
        annotations.replace("no", False, inplace=True)
        annotations.replace("si", True, inplace=True)

        # load file paths
        annotations["path"] = annotations["path"].apply(lambda x: f"{DOCS_PATH}/{x}")

        # set dtypes
        annotations = self.enforce_dtypes(annotations, dtypes=FIELDS)

        data = []
        GROUPBY_COLUMNS = ["nro_registro", "tomo", "path"]
        for keys, group in annotations.groupby(GROUPBY_COLUMNS):

            data_ = {}
            data_["path"] = keys[2]
            data_["metadata"] = {
                "nro_registro": keys[0],
                "tomo": int(keys[1]),
                "extension": get_extension(data_["path"]),
                "n_annotations": len(group),
                "violencia_de_genero": any(group["violencia_de_genero"]),
                "frases_agresion": any(group["frases_agresion"].dropna().astype(bool)),
                "detalle": group["detalle"].dropna().to_list(),
                "objeto_de_la_resolucion": group["objeto_de_la_resolucion"]
                .dropna()
                .to_list(),
                "tipo_de_resolucion": group["tipo_de_resolucion"].dropna().to_list(),
            }

            annotations = group.loc[:, FIELDS.keys()].to_dict("records")

            # force to use None instead of other nan types
            data_["annotations"] = {
                "records": [
                    {k: (v if pd.notna(v) else None) for k, v in anno.items()}
                    for anno in annotations
                ]
            }
            data.append(data_)

        data = filter(
            lambda x: x["metadata"]["extension"] in ["pdf", "odt", "doc", "docx"],
            data,
        )
        data = list(data)

        self.data = data

        if use_cache:
            cache_save(self.data, cache_key, logger)
