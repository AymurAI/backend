from fastapi import HTTPException


class AymuraiAPIException(HTTPException):
    status_code: int
    title: str

    def __init__(self, status_code: int = None, detail: str = None):
        self.status_code = status_code or self.status_code
        self.detail = f"{self.title}: {detail}" if detail else self.title
        super().__init__(status_code=self.status_code, detail=detail)


class UnsupportedFileType(AymuraiAPIException):
    status_code = 400
    title = "Unsupported file type"
