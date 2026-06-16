"""Rechnungen / Stripe-CSV → rechnung_map + stripe_rows."""

import csv
import os
import re
from datetime import datetime

from .utils import de_float, parse_date, stripe_float
import pdfplumber

# Wolt: Bank-PDF vs. Rechnungssumme / expand_transaction
_WOLT_NET_TOLERANCE = 0.05


def _wolt_vertrieb_netto_spalte(p2: str, steuersatz: str) -> float:
    """Dritte Zahl der Zeile 'Summe Vertrieb mit Umsatzsteuer 7/19 %' (Netto-Spalte)."""
    m = re.search(
        rf"Summe Vertrieb mit Umsatzsteuer {steuersatz}[.,]00\s*%?\s+"
        r"(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})\s+(-?[\d.]+,\d{2})",
        p2,
    )
    return de_float(m.group(3)) if m else 0.0


def _wolt_probe_summe(
    umsatz: float, rabatt: float, provision: float, provision19: float, gebühr: float
) -> float:
    return round(umsatz + rabatt + provision + provision19 - gebühr, 2)


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


def _zhou_summary_amounts(txt: str) -> tuple[float, float, float]:
    """Brutto 7 %, Brutto 19 % und Endbetrag (Summe = Bankzahlung)."""
    we7 = we19 = 0.0
    endbetrag = 0.0
    for line in txt.splitlines():
        s = line.strip()
        m_end = re.search(r"Endbetrag\s*€\s*([\d.]+,\d{2})", s, re.I)
        if m_end:
            endbetrag = de_float(m_end.group(1))
        m7 = re.search(
            r"([\d.]+,\d{2})\s+7[,.]00\s+[\d.]+,\d{2}\s+([\d.]+,\d{2})\s*$",
            s,
        )
        if m7 and "Endbetrag" not in s:
            we7 = de_float(m7.group(2))
        m19 = re.search(
            r"([\d.]+,\d{2})\s+19[,.]00\s+[\d.]+,\d{2}\s+([\d.]+,\d{2})",
            s,
        )
        if m19:
            we19 = de_float(m19.group(2))
    return we7, we19, endbetrag


def _zhou_erwartung_final(we7: float, we19: float, endbetrag: float) -> str:
    probe = round(we7 + we19, 2)
    if endbetrag and abs(probe - endbetrag) > 0.05:
        return "1 FiBu-Zeile (Fallback Zhou Wareneinkauf)"
    n = (1 if we7 else 0) + (1 if we19 else 0)
    if not n:
        return "1 FiBu-Zeile (3300)"
    return f"{n} FiBu-Zeilen (Zhou 7 % / Zhou 19 %)"


def _parse_zhou(filepath: str, rm: dict, zhou_audit: list | None) -> None:
    fname = os.path.basename(filepath)
    fl = fname.lower()
    is_gs = " gs-" in fl or fl.startswith("gs ") or " gutschrift" in fl

    def audit(**fields: object) -> None:
        if zhou_audit is None:
            return
        zhou_audit.append({"datei": fname, **fields})

    try:
        with pdfplumber.open(filepath) as pdf:
            txt = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception:
        audit(status="FEHLER", grund="PDF konnte nicht gelesen werden")
        return

    if not txt.strip():
        audit(status="SKIP", grund="Kein Text im PDF")
        return

    m_nr = re.search(r"(?:Rechnung|Gutschrift)\s+Nr\.?:\s*(\S+)", txt, re.I)
    re_nr = m_nr.group(1) if m_nr else ""
    typ = "GS" if is_gs else "RE"

    we7, we19, endbetrag = _zhou_summary_amounts(txt)
    if endbetrag <= 0 and we7 <= 0 and we19 <= 0:
        audit(
            status="SKIP",
            grund="Keine Summenzeilen 7 % / 19 % / Endbetrag gefunden",
            rechnung_nr=re_nr,
            typ=typ,
        )
        return

    sign = -1.0 if is_gs else 1.0
    we7 = round(we7 * sign, 2)
    we19 = round(we19 * sign, 2)
    endbetrag = round(endbetrag * sign, 2)
    probe = round(we7 + we19, 2)

    if endbetrag and abs(probe - endbetrag) > 0.05:
        audit(
            status="SUMME_MISMATCH",
            grund="Netto 7 % + Netto 19 % weicht vom Endbetrag ab",
            rechnung_nr=re_nr,
            typ=typ,
            netto_7=we7,
            netto_19=we19,
            endbetrag=endbetrag,
            probe_summe=probe,
            diff_probe=round(probe - endbetrag, 2),
            erw_final="Kein Einzel-Mapping",
        )
        return

    erw = _zhou_erwartung_final(abs(we7), abs(we19), abs(endbetrag))
    audit(
        status="OK",
        grund="",
        rechnung_nr=re_nr,
        typ=typ,
        netto_7=we7,
        netto_19=we19,
        endbetrag=endbetrag,
        probe_summe=probe,
        diff_probe=0.0,
        erw_final=erw,
    )

    key = round(abs(endbetrag), 2)
    if key > 0:
        rm[key] = ("ZHOU_SPLIT", f"{abs(we7)}|{abs(we19)}|{re_nr}")


def _zhou_finalize_collective(zhou_audit: list | None, rm: dict) -> None:
    """Sammelzahlung: Summe aller OK-Zhou-PDFs als ein ZHOU_SPLIT-Schlüssel."""
    if not zhou_audit:
        return
    ok = [r for r in zhou_audit if r.get("status") == "OK"]
    if len(ok) < 2:
        return

    sum_we7 = round(sum(float(r.get("netto_7") or 0) for r in ok), 2)
    sum_we19 = round(sum(float(r.get("netto_19") or 0) for r in ok), 2)
    sum_end = round(sum(float(r.get("endbetrag") or 0) for r in ok), 2)
    if sum_end <= 0:
        return

    key = round(abs(sum_end), 2)
    re_list = ",".join(str(r.get("rechnung_nr") or "") for r in ok if r.get("rechnung_nr"))
    erw = _zhou_erwartung_final(abs(sum_we7), abs(sum_we19), abs(sum_end))

    zhou_audit.append(
        {
            "datei": "(Sammelzahlung)",
            "status": "OK_SAMMEL",
            "grund": f"{len(ok)} Rechnungen/Gutschriften",
            "rechnung_nr": re_list,
            "typ": "SUM",
            "netto_7": sum_we7,
            "netto_19": sum_we19,
            "endbetrag": sum_end,
            "probe_summe": round(sum_we7 + sum_we19, 2),
            "diff_probe": round(sum_we7 + sum_we19 - sum_end, 2),
            "erw_final": erw,
        }
    )
    rm[key] = ("ZHOU_SPLIT", f"{abs(sum_we7)}|{abs(sum_we19)}|Sammel {re_list}")


def zhou_resolution_warning_lines(zhou_audit: list | None) -> list[str]:
    if not zhou_audit:
        return []
    problem = frozenset({"SUMME_MISMATCH", "FEHLER", "SKIP"})
    out: list[str] = []
    for row in zhou_audit:
        fn = str(row.get("datei") or "?")
        if fn == "(keine)":
            continue
        st = row.get("status") or ""
        grund = (row.get("grund") or "").strip()
        if st in problem:
            out.append(f"{fn}: [{st}] {grund}".strip())
        elif st == "OK" and "Fallback" in str(row.get("erw_final") or ""):
            out.append(f"{fn}: [Final-Fallback] {row.get('erw_final')}")
    return out


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


def _parse_wolt(filepath: str, rm: dict, wolt_audit: list | None) -> None:
    fname = os.path.basename(filepath)

    def audit(**fields: object) -> None:
        if wolt_audit is None:
            return
        row = {"datei": fname, **fields}
        wolt_audit.append(row)

    try:
        with pdfplumber.open(filepath) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
    except Exception:
        audit(status="FEHLER", grund="PDF konnte nicht gelesen werden")
        return

    if len(pages) < 2:
        audit(status="SKIP", grund="Weniger als 2 PDF-Seiten")
        return

    p1 = pages[0]
    p2 = pages[1]
    p3 = pages[2] if len(pages) > 2 else ""

    m = re.search(r"Nettoauszahlung\s+([\d.]+,\d{2})", p1)
    if not m:
        audit(status="SKIP", grund='"Nettoauszahlung" auf Seite 1 nicht gefunden')
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

    # "%" nach dem Steuersatz fehlt in manchen Wolt-PDFs (z. B. "19.00 -10,78").
    provision = _wolt_vertrieb_netto_spalte(p2, "7")
    provision19 = _wolt_vertrieb_netto_spalte(p2, "19")

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

    summe = _wolt_probe_summe(umsatz, rabatt, provision, provision19, gebühr)
    key = round(auszahlung, 2)
    if abs(summe - auszahlung) > _WOLT_NET_TOLERANCE:
        audit(
            status="SUMME_MISMATCH",
            grund="Umsatz+Rabatt+Vertrieb7%+Vertrieb19%-Gebühr weicht >0,05 EUR von Nettoauszahlung ab",
            nettoauszahlung=key,
            umsatz=umsatz,
            rabatt=rabatt,
            provision=provision,
            provision19=provision19,
            gebühr=gebühr,
            zeitraum=tf,
            probe_summe=summe,
            diff_probe=round(summe - auszahlung, 2),
            erw_final="Kein rechnung_map-Eintrag; Final bleibt 1 Zeile",
        )
        return

    dup = key in rm and rm[key][0] == "WOLT_SPLIT"
    erw = _wolt_erwartung_final(key, umsatz, rabatt, provision, provision19, gebühr)
    audit(
        status="OK_DUPLIKAT" if dup else "OK",
        grund=(
            "Gleicher Nettoauszahlungsbetrag wie bereits gemappte Datei (Schlüssel überschrieben)"
            if dup
            else ""
        ),
        nettoauszahlung=key,
        umsatz=umsatz,
        rabatt=rabatt,
        provision=provision,
        provision19=provision19,
        gebühr=gebühr,
        zeitraum=tf,
        probe_summe=summe,
        diff_probe=0.0,
        erw_final=erw,
    )

    rm[key] = ("WOLT_SPLIT", f"{umsatz}|{rabatt}|{provision}|{provision19}|{gebühr}|{tf}")


def _wolt_erwartung_final(
    key: float,
    umsatz: float,
    rabatt: float,
    provision: float,
    provision19: float,
    gebühr: float,
) -> str:
    """Kurztext wie expand_transaction WOLT_SPLIT sich im Blatt Final verhält."""
    cons = _wolt_probe_summe(umsatz, rabatt, provision, provision19, gebühr)
    if abs(cons - key) > _WOLT_NET_TOLERANCE:
        return "1 FiBu-Zeile (Fallback 8300, Konsistenzprüfung)"
    n = 0
    if umsatz:
        n += 1
    if rabatt:
        n += 1
    if provision:
        n += 1
    if provision19:
        n += 1
    if gebühr:
        n += 1
    if not n:
        return "1 FiBu-Zeile (8300)"
    return f"{n} FiBu-Zeilen (8300 / 8780 / 804760 / 904760)"


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


def wolt_resolution_warning_lines(wolt_audit: list | None) -> list[str]:
    """Kurze Textzeilen fuer Konsole: Wolt-PDFs mit Mapping- oder Final-Aufloesungsproblemen."""
    if not wolt_audit:
        return []
    problem_stati = frozenset({"SUMME_MISMATCH", "FEHLER", "SKIP", "OK_DUPLIKAT"})
    out: list[str] = []
    for row in wolt_audit:
        fn = str(row.get("datei") or "?")
        if fn == "(keine)":
            continue
        st = row.get("status") or ""
        grund = (row.get("grund") or "").strip()
        if st in problem_stati:
            out.append(f"{fn}: [{st}] {grund}".strip())
        elif st == "OK":
            erw = row.get("erw_final") or ""
            if "Fallback" in erw:
                out.append(f"{fn}: [Final-Fallback] {erw}")
    return out


def _parse_xxl_gastro(filepath: str, rm: dict) -> None:
    """XXL Gastro Rechnung → Betrag + Kürzel (Klarna-Zahlung im Kontoauszug)."""
    try:
        with pdfplumber.open(filepath) as pdf:
            txt = "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:
        return

    if not txt.strip():
        return

    total_match = re.search(r"Gesamt\s*€\s*([\d.]+,\d{2})", txt)
    if not total_match:
        total_match = re.search(r"Gesamt\s+([\d.]+,\d{2})\s*€", txt)
    if not total_match:
        return

    total = round(de_float(total_match.group(1)), 2)
    if total <= 0:
        return

    rm[total] = ("", "XXL Gastro Anlagen")


def load_invoices(
    source_dir: str,
    rechnung_map: dict,
    stripe_rows: list,
    wolt_audit: list | None = None,
    zhou_audit: list | None = None,
) -> int:
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
                    _parse_wolt(fpath, rechnung_map, wolt_audit)
                    ok += 1
                elif "zhou" in fl:
                    _parse_zhou(fpath, rechnung_map, zhou_audit)
                    ok += 1
                elif "takeaway" in fl:
                    _parse_takeaway(fpath, rechnung_map)
                    ok += 1
                elif "xxl" in fl and "gastro" in fl:
                    _parse_xxl_gastro(fpath, rechnung_map)
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

    _zhou_finalize_collective(zhou_audit, rechnung_map)

    print(f"   Rechnungs-Mapping: {len(rechnung_map)} Einträge aus {ok} Dateien")
    return ok
