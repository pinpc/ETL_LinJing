"""pdfminer-Warnungen (FontBBox) unterdrücken — vor import pdfplumber aufrufen."""

import logging

_PDF_LOGGERS = (
    "pdfminer",
    "pdfminer.pdffont",
    "pdfminer.pdfinterp",
    "pdfminer.pdfpage",
    "pdfplumber",
)


def silence_pdfminer() -> None:
    for name in _PDF_LOGGERS:
        logging.getLogger(name).setLevel(logging.ERROR)
