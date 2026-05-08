import json
import re
import logging
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger("app.core.parsers")

# ---------------------------------------------------------------------------
# Thai Buddhist Era helpers
# ---------------------------------------------------------------------------

_THAI_MONTH_MAP = {
    "ม.ค.": 1,  "มกราคม": 1,
    "ก.พ.": 2,  "กุมภาพันธ์": 2,
    "มี.ค.": 3, "มีนาคม": 3,
    "เม.ย.": 4, "เมษายน": 4,
    "พ.ค.": 5,  "พฤษภาคม": 5,
    "มิ.ย.": 6, "มิถุนายน": 6,
    "ก.ค.": 7,  "กรกฎาคม": 7,
    "ส.ค.": 8,  "สิงหาคม": 8,
    "ก.ย.": 9,  "กันยายน": 9,
    "ต.ค.": 10, "ตุลาคม": 10,
    "พ.ย.": 11, "พฤศจิกายน": 11,
    "ธ.ค.": 12, "ธันวาคม": 12,
}


def _be_year_to_ad(year: int) -> int:
    """Convert Buddhist Era year to AD. Years >= 2400 are treated as BE."""
    return year - 543 if year >= 2400 else year


def _parse_date_string(raw: Optional[str]) -> Optional[date]:
    """
    Best-effort parser for the many date formats that appear across document
    classes in this system. Returns a `datetime.date` or None.

    Handles:
      • ISO-8601:         "2025-02-03", "2025-02-03T14:00:00"
      • Thai short:       "3 ก.พ. 69"  (BE two-digit year)
      • Thai long:        "3 กุมภาพันธ์ 2568"
      • DD/MM/YYYY:       "03/02/2025", "03/02/68"  (BE two-digit)
      • Thai date-time:   "03/02/2568 14:00"
      • Slash ISO:        "2025/02/03"
      • Ranges (takes first date):  "3-5 ก.พ. 69", "03/02/68 - 05/02/68"
    """
    if not raw:
        return None

    raw = str(raw).strip()

    # --- strip time component ---
    raw_no_time = re.split(r"\s+\d{1,2}:\d{2}", raw)[0].strip()

    # --- handle ranges: take the first date ---
    raw_no_time = re.split(r"\s*[-–]\s*\d", raw_no_time)[0].strip()

    # 1. ISO-8601: YYYY-MM-DD or YYYY/MM/DD
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", raw_no_time)
    if m:
        y, mo, d_ = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = _be_year_to_ad(y)
        try:
            return date(y, mo, d_)
        except ValueError:
            pass

    # 2. Thai textual: "3 ก.พ. 69" or "3 กุมภาพันธ์ 2568"
    for th_month, month_num in _THAI_MONTH_MAP.items():
        pattern = rf"(\d{{1,2}})\s+{re.escape(th_month)}\s+(\d{{2,4}})"
        m = re.search(pattern, raw_no_time)
        if m:
            day_ = int(m.group(1))
            year_ = int(m.group(2))
            if year_ < 100:          # two-digit BE: 69 → 2569 → 2026
                year_ += 2500
            year_ = _be_year_to_ad(year_)
            try:
                return date(year_, month_num, day_)
            except ValueError:
                pass

    # 3. DD/MM/YYYY or DD/MM/YY (BE)
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", raw_no_time)
    if m:
        d_, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2500
        y = _be_year_to_ad(y)
        try:
            return date(y, mo, d_)
        except ValueError:
            pass

    logger.debug(f"_parse_date_string: could not parse '{raw}'")
    return None


# ---------------------------------------------------------------------------
# Per-document-class date range extractor
# ---------------------------------------------------------------------------

def extract_date_ranges(doc: dict) -> dict:
    """
    Returns a normalised dict describing every date boundary found in *doc*:

        {
            "doc_class":   str,
            "filename":    str,
            "date_start":  date | None,   # earliest relevant date
            "date_end":    date | None,   # latest relevant date  (=date_start for point dates)
            "raw_dates":   { label: raw_string }   # for human-readable warnings
        }

    The mapping follows the exact JSON schemas produced by CLASSIFIER_SYSTEM_PROMPT.
    """
    doc_class = doc.get("document_class", "Unknown")
    filename  = doc.get("filename", "")
    raw_dates: dict = {}
    dates_found: list[date] = []

    def _add(label: str, raw: Optional[str]):
        if not raw:
            return
        raw_dates[label] = raw
        parsed = _parse_date_string(raw)
        if parsed:
            dates_found.append(parsed)

    # ---- Category 1: Receipt / Tax Invoice / Cash Bill ----
    if doc_class == "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด":
        _add("payment_date", doc.get("payment_date"))

    # ---- Category 2: empeo Approval ----
    elif doc_class == "ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo":
        empeo = doc.get("empeo_details", {})
        _add("transaction_date", empeo.get("transaction_date"))
        # duration is typically a range string like "3-5 ก.พ. 69"
        _add("duration_start", empeo.get("duration"))
        # try to also parse the end of the range
        dur_raw = empeo.get("duration", "")
        if dur_raw:
            # pattern: "DD[-–]DD MONTH YEAR"  →  extract end day
            m = re.match(
                r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s+(.+)",
                str(dur_raw).strip()
            )
            if m:
                end_fragment = f"{m.group(2)} {m.group(3)}"
                _add("duration_end", end_fragment)

    # ---- Category 3: Travel Report ----
    elif doc_class == "รายงานการเดินทาง":
        itinerary = doc.get("travel_report_details", {}).get("itinerary", [])
        for i, row in enumerate(itinerary):
            _add(f"row{i}_departure", row.get("departure_datetime"))
            _add(f"row{i}_arrival",   row.get("arrival_datetime"))

    # ---- Category 4: Schedule ----
    elif doc_class == "กำหนดการ":
        _add("event_dates", doc.get("schedule_details", {}).get("event_dates"))

    # ---- Category 5: Itinerary ----
    elif doc_class == "Itinerary":
        for i, flight in enumerate(doc.get("itinerary_details", {}).get("flights", [])):
            _add(f"flight{i}_date", flight.get("date"))

    # ---- Category 6: Original Invoice ----
    elif doc_class == "ต้นฉบับใบแจ้งหนี้":
        _add("invoice_date", doc.get("invoice_details", {}).get("invoice_date"))

    # ---- Category 7: Allowance Calculation Form ----
    elif doc_class == "แบบฟอร์มการคำนวณเบี้ยเลี้ยง":
        summary = doc.get("allowance_details", {}).get("summary", {})
        _add("start_datetime", summary.get("start_datetime"))
        _add("end_datetime",   summary.get("end_datetime"))

    # ---- Category 8: Hotel Folio ----
    elif doc_class == "รายละเอียดการเข้าพัก (Folio)":
        folio = doc.get("folio_details", {})
        _add("check_in_date",  folio.get("check_in_date"))
        _add("check_out_date", folio.get("check_out_date"))

    date_start = min(dates_found) if dates_found else None
    date_end   = max(dates_found) if dates_found else None

    return {
        "doc_class":  doc_class,
        "filename":   filename,
        "date_start": date_start,
        "date_end":   date_end,
        "raw_dates":  raw_dates,
    }


def _parse_json_result(result_text: str) -> dict:
    """Helper to safely parse JSON strings returned by LLMs."""
    # Clean up markdown code blocks
    if result_text.strip().startswith("```"):
        result_text = result_text.strip().split("\n", 1)[-1]
        if result_text.strip().endswith("```"):
            result_text = result_text.strip().rsplit("\n", 1)[0]

    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        # Retry with substring search
        start = result_text.find("{")
        end = result_text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(result_text[start:end+1])
            except:
                pass
        raise Exception("Failed to parse JSON response: " + result_text[:100] + "...")
