from aymurai.logger import get_logger
from aymurai.text.extractors.utils import get_marker_pdf_converter_and_md_renderer

logger = get_logger(__name__)


def warm_marker_models() -> None:
    """Download marker-pdf artifacts at startup to avoid first-request latency."""
    try:
        get_marker_pdf_converter_and_md_renderer()
        logger.info("marker-pdf models are ready")
    except Exception as exc:
        logger.warning("marker-pdf warmup failed: %s", exc)
