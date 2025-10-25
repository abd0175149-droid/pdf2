
from . import compress, convert, files, merge, ocr, split, watermark

routers = [
    ocr.router,
    merge.router,
    split.router,
    compress.router,
    convert.router,
    watermark.router,
    files.router,
]

__all__ = [
    "routers",
]
