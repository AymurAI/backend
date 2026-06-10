from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response

from aymurai.settings import settings

router = APIRouter(include_in_schema=False)

LEGACY_API_ROUTE_PREFIXES = (
    "anonymizer",
    "api",
    "convert",
    "datapublic",
    "database",
    "document-extract",
    "docs",
    "misc",
    "openapi.json",
    "redoc",
    "server",
)
FEATURE_ROUTE_SLUGS = ("anonymizer", "data_set")
FEATURE_ROUTE_STEPS = ("", "finish", "onboarding", "preview", "process", "validation")
LEGACY_FEATURE_ROUTE_SLUGS = {
    "ANONYMIZER": "anonymizer",
    "DATA_SET": "data_set",
}


def _frontend_dist_dir() -> Path:
    return Path(settings.FRONTEND_DIST_DIR).expanduser()


def _split_asset_path(asset_path: str) -> list[str]:
    return [segment for segment in asset_path.lstrip("/").split("/") if segment]


def _is_frontend_feature_route(asset_path: str) -> bool:
    segments = _split_asset_path(asset_path)
    if not segments or segments[0] not in FEATURE_ROUTE_SLUGS:
        return False

    return len(segments) == 1 or segments[1] in FEATURE_ROUTE_STEPS


def _is_legacy_api_route(asset_path: str) -> bool:
    first_segment = asset_path.lstrip("/").split("/", maxsplit=1)[0]
    if _is_frontend_feature_route(asset_path):
        return False
    return first_segment in LEGACY_API_ROUTE_PREFIXES


def _canonical_frontend_path(asset_path: str) -> str | None:
    segments = _split_asset_path(asset_path)
    if not segments:
        return None

    if segments[0] == "app":
        canonical_segments = segments[1:]
        if canonical_segments:
            canonical_feature = LEGACY_FEATURE_ROUTE_SLUGS.get(canonical_segments[0])
            if canonical_feature:
                canonical_segments = [canonical_feature, *canonical_segments[1:]]
        return "/" + "/".join(canonical_segments)

    canonical_feature = LEGACY_FEATURE_ROUTE_SLUGS.get(segments[0])
    if canonical_feature:
        return "/" + "/".join([canonical_feature, *segments[1:]])

    return None


def _resolve_frontend_path(asset_path: str) -> Path:
    dist_dir = _frontend_dist_dir().resolve()
    requested_path = (dist_dir / asset_path.lstrip("/")).resolve()
    requested_path.relative_to(dist_dir)
    return requested_path


def _serve_frontend(asset_path: str = "") -> Response:
    canonical_path = _canonical_frontend_path(asset_path)
    if canonical_path is not None:
        return RedirectResponse(canonical_path or "/")

    if asset_path and _is_legacy_api_route(asset_path):
        raise HTTPException(status_code=404, detail="API route not found.")

    dist_dir = _frontend_dist_dir()
    index_file = dist_dir / "index.html"
    if not dist_dir.is_dir() or not index_file.is_file():
        raise HTTPException(status_code=404, detail="Frontend build not found.")

    if asset_path:
        try:
            requested_path = _resolve_frontend_path(asset_path)
        except ValueError as error:
            raise HTTPException(
                status_code=404, detail="Frontend asset not found."
            ) from error

        if requested_path.is_file():
            return FileResponse(requested_path)

        if Path(asset_path).suffix:
            raise HTTPException(status_code=404, detail="Frontend asset not found.")

    return FileResponse(index_file)


@router.get("/")
@router.get("/{asset_path:path}")
async def frontend_app(asset_path: str = "") -> Response:
    return _serve_frontend(asset_path)
