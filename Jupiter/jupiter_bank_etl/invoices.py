"""Rechnungen / Stripe-CSV → rechnung_map + stripe_rows."""

import csv
import os
import re
from datetime import datetime

from .utils import de_float, parse_date, stripe_float
import pdfplumber


def _parse_hamberger(filepath: str, rm: dict) -> None:
    try:
        with pdfplumber.open(filepath) as pdf:
            txt = ""
            for page in reversed(pdf.pages):
                t = page.extract_text() or ""
                if t.strip():
                    txt = t
                    break
    except Exception:
        return

    if not txt.strip():
        return

    date_s = re.search(r"(\d{2}\.\d{2}\.\d{4})", os.path.basename(filepath))
    ds = parse_date(date_s.group(1)).strftime("%d.%m.%Y") if date_s else ""

    we7 = we19 = 0.0
    for line in txt.split("\n"):
        m7 = re.search(
            r"7,00\s+[\d.]+,\d{2}\s+[\d.]+,\d{2}-?\s+[\d.]+,\d{2}-?\s+"
            r"([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})",
            line,
        )
        if m7:
            we7 = de_float(m7.group(3))

        m19 = re.search(
            r"19,00\s+[\d.]+,\d{2}\s+[\d.]+,\d{2}-?\s+[\d.]+,\d{2}-?\s+"
            r"([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})",
            line,
        )
        if m19:
            we19 = de_float(m19.group(3))

    gesamt = round(we7 + we19, 2)
    if gesamt <= 0:
        return

    key = gesamt
    if we7 > 0 and we19 > 0:
        rm[key] = ("HAMBERGER_SPLIT", f"{we7}|{we19}|{ds}")
    elif we7 > 0:
        rm[key] = ("HAMBERGER_SPLIT", f"{we7}|0|{ds}")


def _parse_uber(filepath: str, rm: dict) -> None:
    try:
        with pdfplumber.open(filepath) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
    except Exception:
        return

    if not pages:
        return

    p1 = pages[0]
    txt = "\n".join(pages)

    tf_m = re.search(r"vom\s+(\d{2}\.\d{2}\.\d{4})\s+bis zum\s+(\d{2}\.\d{2}\.\d{4})", p1)
    tf = ""
    if tf_m:
        d1 = parse_date(tf_m.group(1))
        d2 = parse_date(tf_m.group(2))
        tf = f"{d1.strftime('%d.%m.%y')} - {d2.strftime('%d.%m.%y')}" if d1 and d2 else ""

    def grab(pat, text):
        m = re.search(pat, text, re.DOTALL)
        return de_float(m.group(1)) if m else 0.0

    auszahlung = grab(r"Gesamtauszahlung\s*€\s*([\d.]+,\d{2})", p1)
    umsatz = grab(r"Gesamtwert von:\s*€\s*([\d.]+,\d{2})", p1)
    rabatt = grab(r"Rabatte\s*/Angebote.*?€\s*-\s*([\d.]+,\d{2})", p1)
    gebühr = grab(r"Uber Eats Gebühr\s*€\s*([\d.]+,\d{2})", p1)
    mwst = grab(r"MwSt\.\s*\(19%.*?\)\s*€\s*([\d.]+,\d{2})", p1)
    offer = grab(r"Angebotsgebühr.*?€\s*-\s*([\d.]+,\d{2})", p1)
    invoice_total = grab(r"Gesamtbetrag\s+([\d.]+,\d{2})\s*€", txt)

    prov = round(invoice_total, 2) if invoice_total > 0 else round(gebühr + mwst + offer, 2)

    if auszahlung and umsatz:
        split_sum = round(umsatz - rabatt - prov, 2)
        if abs(split_sum - auszahlung) > 0.05:
            # Reconcile the split to the bank payout if Uber's summary page
            # and invoice page differ slightly because of cross-period adjustments.
            prov = round(umsatz - rabatt - auszahlung, 2)
        rm[round(auszahlung, 2)] = ("UBER_SPLIT", f"{umsatz}|{rabatt}|{prov}|{tf}")


def _parse_stripe(filepath: str, rm: dict, stripe_rows: list) -> None:
    date_m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(filepath))
    if not date_m:
        return
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return
    first = content.split("\n")[0]
    sep = ";" if first.count(";") > first.count(",") else ","
    try:
        reader = csv.DictReader(content.splitlines(), delimiter=sep)
        rows = list(reader)
    except Exception:
        return
    if not rows:
        return
    keys = [k for k in rows[0].keys() if k]
    amt_k = next((k for k in keys if k.strip('"') == "amount"), None)
    fee_k = next((k for k in keys if k.strip('"') == "feeAmount"), None)
    if not (amt_k and fee_k):
        return
    total_amount = total_fee = 0.0
    for row in rows:
        raw_amt = str(row.get(amt_k, "0")).strip()
        raw_fee = str(row.get(fee_k, "0")).strip()
        if re.search(r"[a-df-z]", raw_amt, re.IGNORECASE):
            continue
        if re.search(r"[a-df-z]", raw_fee, re.IGNORECASE):
            raw_fee = "0"
        if not raw_fee.strip():
            continue
        a = stripe_float(raw_amt)
        f_ = stripe_float(raw_fee)
        if a > 0:
            total_amount += a
            total_fee += f_
    if total_amount <= 0:
        return
    total_amount = round(total_amount, 2)
    total_fee = round(total_fee, 2)
    csv_date = parse_date(date_m.group(1))
    ds = csv_date.strftime("%d.%m.%y") if csv_date else ""
    rm[total_amount] = ("STRIPE_SPLIT", f"{total_fee}")
    stripe_rows.append({"date": csv_date, "ds": ds, "amount": total_amount, "fee": total_fee})


def _parse_wolt(filepath: str, rm: dict) -> None:
    try:
        with pdfplumber.open(filepath) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
    except Exception:
        return

    if len(pages) < 2:
        return

    p1 = pages[0]
    p2 = pages[1]
    p3 = pages[2] if len(pages) > 2 else ""

    m = re.search(r"Nettoauszahlung\s+([\d.]+,\d{2})", p1)
    if not m:
        return
    auszahlung = de_float(m.group(1))

    tf_m = re.search(
        r"Leistungszeitraum\s+(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})", p2
    )
    if tf_m:
        d1 = datetime.strptime(tf_m.group(1), "%d.%m.%Y")
        d2 = datetime.strptime(tf_m.group(2), "%d.%m.%Y")
        tf = f"{d1.strftime('%d.%m.%y')} - {d2.strftime('%d.%m.%y')}"
    else:
        tf = ""

    m = re.search(
        r"Summe verkaufte Waren\s+[\d.]+,\d{2}\s+[\d.]+\s+[\d.]+,\d{2}\s+([\d.]+,\d{2})", p2
    )
    umsatz = de_float(m.group(1)) if m else 0.0

    m = re.search(
        r"Summe Vergütungen\s+(-?[\d.]+,\d{2})\s+[\d.]+\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})",
        p2,
    )
    vergütungen = de_float(m.group(3)) if m else 0.0

    m = re.search(
        r"rabattierten Artikel\s+(-?[\d.]+,\d{2})\s+[\d.]+\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})",
        p2,
    )
    haendlerrabatt = de_float(m.group(3)) if m else 0.0

    rabatt = round(vergütungen + haendlerrabatt, 2)

    m = re.search(
        r"Summe Vertrieb mit Umsatzsteuer 7[.,]00\s*%\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})",
        p2,
    )
    provision = de_float(m.group(3)) if m else 0.0

    gebühr = 0.0
    if p3:
        dl_block = p3.split("Wolt Dienstleistungen")[-1] if "Wolt Dienstleistungen" in p3 else ""
        m_dl = re.search(r"Summe\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})", dl_block)
        if m_dl:
            gebühr += de_float(m_dl.group(3))
        zus_block = p3.split("Zusätzliche Gebühren")[-1] if "Zusätzliche Gebühren" in p3 else ""
        m_zus = re.search(r"Summe\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})\s+([\d.]+,\d{2})", zus_block)
        if m_zus:
            gebühr += de_float(m_zus.group(3))
    gebühr = round(gebühr, 2)

    summe = round(umsatz + rabatt + provision - gebühr, 2)
    if abs(summe - auszahlung) > 0.05:
        return

    rm[round(auszahlung, 2)] = ("WOLT_SPLIT", f"{umsatz}|{rabatt}|{provision}|{gebühr}|{tf}")


def _parse_takeaway(filepath: str, rm: dict) -> None:
    try:
        with pdfplumber.open(filepath) as pdf:
            p1 = pdf.pages[0].extract_text() or ""
            p2 = pdf.pages[1].extract_text() if len(pdf.pages) > 1 else ""
    except Exception:
        return

    txt = p1 + "\n" + p2

    tf_m = re.search(r"(\d{2}-\d{2}-\d{4})\s+bis\s+einschl[^\d]*(\d{2}-\d{2}-\d{4})", txt)
    if tf_m:
        d1 = datetime.strptime(tf_m.group(1), "%d-%m-%Y")
        d2 = datetime.strptime(tf_m.group(2), "%d-%m-%Y")
        tf = f"{d1.strftime('%d.%m.%y')} - {d2.strftime('%d.%m.%y')}"
    else:
        tf = ""

    m_umsatz = re.search(r"Ausstehende Onlinebezahlungen.*?€\s*([\d.]+,\d{2})", txt)
    umsatz = de_float(m_umsatz.group(1)) if m_umsatz else 0.0

    m_gebühr = re.search(r"Rechnungsausgleich\s+\d+\s+€\s*([\d.]+,\d{2})", txt)
    gebühr = de_float(m_gebühr.group(1)) if m_gebühr else 0.0

    m_ausz = re.search(r"Zu begleichender Betrag:\s*€\s*([\d.]+,\d{2})", txt)
    if m_ausz:
        auszahlung = de_float(m_ausz.group(1))
    elif umsatz and gebühr:
        auszahlung = round(umsatz - gebühr, 2)
    else:
        return

    if not auszahlung:
        return

    if abs(round(umsatz - gebühr, 2) - auszahlung) > 0.05:
        return

    rm[round(auszahlung, 2)] = ("TAKEAWAY_SPLIT", f"{umsatz}|{gebühr}|{tf}")


def load_invoices(source_dir: str, rechnung_map: dict, stripe_rows: list) -> int:
    """Liest Rechnungen aus source_dir; mutiert rechnung_map und stripe_rows."""
    files = sorted(os.listdir(source_dir))
    ok = skip = 0

    for fname in files:
        fpath = os.path.join(source_dir, fname)
        if not os.path.isfile(fpath):
            continue
        fl = fname.lower()

        try:
            if fl.endswith(".pdf"):
                if "uber" in fl:
                    _parse_uber(fpath, rechnung_map)
                    ok += 1
                elif "hamberger" in fl:
                    _parse_hamberger(fpath, rechnung_map)
                    ok += 1
                elif "wolt" in fl:
                    _parse_wolt(fpath, rechnung_map)
                    ok += 1
                elif "takeaway" in fl:
                    _parse_takeaway(fpath, rechnung_map)
                    ok += 1
                else:
                    skip += 1
            elif fl.endswith(".csv") and "stripe" in fl:
                _parse_stripe(fpath, rechnung_map, stripe_rows)
                ok += 1
            else:
                skip += 1
        except Exception:
            pass

    print(f"   Rechnungs-Mapping: {len(rechnung_map)} Einträge aus {ok} Dateien")
    return ok
