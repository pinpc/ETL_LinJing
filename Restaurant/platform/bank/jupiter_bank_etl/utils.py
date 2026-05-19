"""Kleine Hilfsfunktionen ohne Seiteneffekte."""

from datetime import date, datetime


def de_float(s):
    if s is None:
        return 0.0
    s = str(s).strip().replace("\xa0", "").replace(" ", "").replace('"', "")
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_date(s):
    if isinstance(s, (date, datetime)):
        return s.date() if isinstance(s, datetime) else s
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except Exception:
            pass
    return None


def stripe_float(s):
    if not s:
        return 0.0
    s = str(s).strip().strip('"')
    if not s:
        return 0.0
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return 0.0


def datum_iso(d):
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d) if d is not None else None
