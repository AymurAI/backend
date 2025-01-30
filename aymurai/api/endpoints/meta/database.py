from enum import Enum


class ExportFormat(str, Enum):
    CSV = "csv"
    JSON = "json"
