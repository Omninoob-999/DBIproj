import logging
from datetime import date
from typing import List, Dict, Any, Optional

logger = logging.getLogger("app.core.rules_engine")

def validate_data(extracted_data: dict) -> List[str]:
    """Deterministic checks for financial integrity. (Stage 2: The Controller)"""
    errors = []
    
    if not extracted_data:
        return ["Empty extraction result"]

    # 1. Financial Math Check (New Schema: data.financials.amounts)
    try:
        data_block = extracted_data.get('data', {})
        fin = data_block.get('financials', {})
        amounts = fin.get('amounts', {})
        
        net_amount = amounts.get('net_amount') or 0.0
        tax_amount = amounts.get('tax_amount') or 0.0
        total_amount = amounts.get('total_amount') or 0.0
        
        calculated = round(net_amount + tax_amount, 2)
        if abs(calculated - total_amount) > 0.1:
            errors.append(f"Math Mismatch: Net({net_amount}) + Tax({tax_amount}) != Total({total_amount})")
    except Exception as e:
        errors.append(f"Math check failed: {str(e)}")
    
    # 2. Tax ID Length Check (New Schema: identity.issuer/receiver)
    try:
        identity = extracted_data.get('identity', {})
        for role in ['issuer', 'receiver']:
            entity = identity.get(role, {})
            tax_id = entity.get('tax_id')
            if tax_id:
                clean_tax = str(tax_id).replace("-", "").replace(" ", "")
                # Only warn if it looks like a Thai Tax ID (13 digits) is attempted but wrong length
                if clean_tax.isdigit() and len(clean_tax) != 13:
                     # Some foreign invoices might have diverse tax IDs, so we can be lenient or specific.
                     # For BDI requirements, we expect 13 digits for Thai entities.
                     errors.append(f"Invalid {role} Tax ID length: {tax_id} (Expected 13 digits)")
    except Exception as e:
        errors.append(f"Tax ID check failed: {str(e)}")
            
    return errors

def cross_reference_dates(
    classified_docs: List[Dict[str, Any]],
    date_ranges: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Cross-references dates across all documents in a batch and returns a list
    of warning dicts (never errors — non-blocking by design).

    Checks performed
    ----------------
    1. **Empeo approval coverage** — every receipt, folio, invoice, itinerary,
       travel-report row, and allowance form date must fall *within* the date
       window declared by the empeo approval document.

    2. **Travel-report ↔ receipt/itinerary alignment** — each departure /
       arrival date in the travel report must have at least one matching date
       (±0 days) in a receipt or itinerary document.

    3. **Folio check-in / check-out ↔ receipt date** — the hotel folio dates
       must overlap with or be covered by a hotel receipt's payment_date.

    Each warning dict has the shape::

        {
            "level":    "warning",
            "check":    "<check name>",
            "message":  "<human-readable explanation>",
            "files":    ["filename_a", "filename_b"],   # documents involved
        }
    """
    warnings: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Index documents by class for fast lookup
    # ------------------------------------------------------------------ #
    def _by_class(cls: str) -> List[Dict]:
        return [r for r in date_ranges if r["doc_class"] == cls]

    empeo_ranges   = _by_class("ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo")
    receipt_ranges = _by_class("ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด")
    folio_ranges   = _by_class("รายละเอียดการเข้าพัก (Folio)")
    travel_ranges  = _by_class("รายงานการเดินทาง")
    itin_ranges    = _by_class("Itinerary")
    allow_ranges   = _by_class("แบบฟอร์มการคำนวณเบี้ยเลี้ยง")
    invoice_ranges = _by_class("ต้นฉบับใบแจ้งหนี้")
    schedule_ranges= _by_class("กำหนดการ")

    # ------------------------------------------------------------------ #
    # Helper: build a merged empeo window from all empeo docs in the batch
    # ------------------------------------------------------------------ #
    def _empeo_window() -> tuple[Optional[date], Optional[date]]:
        starts = [r["date_start"] for r in empeo_ranges if r["date_start"]]
        ends   = [r["date_end"]   for r in empeo_ranges if r["date_end"]]
        if not starts:
            return None, None
        return min(starts), max(ends) if ends else max(starts)

    empeo_start, empeo_end = _empeo_window()

    def _within_empeo(d: Optional[date], filename: str, label: str) -> None:
        """Emit a warning if *d* falls outside the empeo window."""
        if d is None or empeo_start is None:
            return
        win_end = empeo_end or empeo_start
        if not (empeo_start <= d <= win_end):
            empeo_files = [r["filename"] for r in empeo_ranges]
            warnings.append({
                "level":   "warning",
                "check":   "empeo_coverage",
                "message": (
                    f"'{label}' date {d} in '{filename}' is outside the empeo "
                    f"approval window {empeo_start} – {win_end}."
                ),
                "files": [filename] + empeo_files,
            })

    # ------------------------------------------------------------------ #
    # Check 1 — Empeo approval coverage
    # ------------------------------------------------------------------ #
    if empeo_ranges:
        # Receipts
        for r in receipt_ranges:
            _within_empeo(r["date_start"], r["filename"], "payment_date")

        # Folios (check-in through check-out must be inside window)
        for r in folio_ranges:
            _within_empeo(r["date_start"], r["filename"], "check_in_date")
            _within_empeo(r["date_end"],   r["filename"], "check_out_date")

        # Allowance forms
        for r in allow_ranges:
            _within_empeo(r["date_start"], r["filename"], "allowance_start")
            _within_empeo(r["date_end"],   r["filename"], "allowance_end")

        # Invoices
        for r in invoice_ranges:
            _within_empeo(r["date_start"], r["filename"], "invoice_date")

        # Itinerary flight dates
        for r in itin_ranges:
            _within_empeo(r["date_start"], r["filename"], "itinerary_date")
            if r["date_end"] and r["date_end"] != r["date_start"]:
                _within_empeo(r["date_end"], r["filename"], "itinerary_date")

        # Travel report rows
        for r in travel_ranges:
            _within_empeo(r["date_start"], r["filename"], "travel_report_date")
            if r["date_end"] and r["date_end"] != r["date_start"]:
                _within_empeo(r["date_end"], r["filename"], "travel_report_date")

    # ------------------------------------------------------------------ #
    # Check 2 — Travel-report dates align with receipts or itineraries
    # ------------------------------------------------------------------ #
    if travel_ranges:
        # Collect all dates that appear on receipts + itineraries
        anchor_dates: set[date] = set()
        for r in receipt_ranges + itin_ranges:
            if r["date_start"]:
                anchor_dates.add(r["date_start"])
            if r["date_end"]:
                anchor_dates.add(r["date_end"])

        if anchor_dates:
            for tr in travel_ranges:
                # Extract every individual date from the travel report doc
                tr_doc = next(
                    (d for d in classified_docs if d.get("filename") == tr["filename"]),
                    {}
                )
                itinerary_rows = tr_doc.get("travel_report_details", {}).get("itinerary", [])

                from core.parsers import _parse_date_string  # local import avoids circular at module level

                for i, row in enumerate(itinerary_rows):
                    for label in ("departure_datetime", "arrival_datetime"):
                        raw = row.get(label)
                        if not raw:
                            continue
                        row_date = _parse_date_string(raw)
                        if row_date and row_date not in anchor_dates:
                            anchor_files = (
                                [r["filename"] for r in receipt_ranges]
                                + [r["filename"] for r in itin_ranges]
                            )
                            warnings.append({
                                "level":   "warning",
                                "check":   "travel_report_alignment",
                                "message": (
                                    f"Travel report '{tr['filename']}' row {i} "
                                    f"{label} {row_date} ({raw!r}) has no matching "
                                    f"date in any receipt or itinerary document."
                                ),
                                "files": [tr["filename"]] + anchor_files,
                            })

    # ------------------------------------------------------------------ #
    # Check 3 — Hotel folio dates covered by a hotel receipt
    # ------------------------------------------------------------------ #
    hotel_receipts = [
        r for r in receipt_ranges
        if next(
            (d for d in classified_docs
             if d.get("filename") == r["filename"]
             and d.get("receipt_type") == "Hotel"),
            None
        )
    ]

    for folio in folio_ranges:
        if folio["date_start"] is None:
            continue
        # Look for a hotel receipt whose payment_date overlaps with check-in..check-out
        folio_end = folio["date_end"] or folio["date_start"]
        covered = any(
            hr["date_start"] is not None
            and folio["date_start"] <= hr["date_start"] <= folio_end
            for hr in hotel_receipts
        )
        if not covered and hotel_receipts:
            warnings.append({
                "level":   "warning",
                "check":   "folio_receipt_alignment",
                "message": (
                    f"Hotel folio '{folio['filename']}' covers "
                    f"{folio['date_start']} – {folio_end} but no hotel receipt "
                    f"payment_date falls within that window."
                ),
                "files": [folio["filename"]] + [r["filename"] for r in hotel_receipts],
            })

    return warnings


def determine_claim_category(classified_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Stage 2: Takes a list of document classification results and applies the company's checklist matrix
    to determine the final expense claim category.
    """
    # Track what we found
    found_classes = set()
    receipt_types = set()
    
    for doc in classified_docs:
        doc_class = doc.get("document_class")
        if doc_class and doc_class != "Unknown":
            found_classes.add(doc_class)
            
        r_type = doc.get("receipt_type")
        if r_type:
            receipt_types.add(r_type)

    logger.info(f"Rule Engine analyzing found documents: {found_classes}")
    logger.info(f"Rule Engine analyzing receipt types: {receipt_types}")

    # --- Matrix Rules ---
    
    # Check 1: Accommodation (ค่าที่พัก)
    accom_required = {
        "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด", 
        "ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo", 
        "รายงานการเดินทาง", 
        "กำหนดการ", 
        "รายละเอียดการเข้าพัก (Folio)"
    }
    if accom_required.issubset(found_classes):
        return {"claim_category": "ค่าที่พัก", "missing_documents": [], "status": "COMPLETE"}

    # Check 2: Airfare (ค่าโดยสารเครื่องบิน)
    airfare_required = {
        "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด", 
        "ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo", 
        "รายงานการเดินทาง", 
        "กำหนดการ", 
        "Itinerary"
    }
    # Note: "ต้นฉบับใบแจ้งหนี้" is optional (marked 'O' in the table), so we don't strictly require it
    if airfare_required.issubset(found_classes):
        return {"claim_category": "ค่าโดยสารเครื่องบิน", "missing_documents": [], "status": "COMPLETE"}

    # Check 3: Allowance (ค่าเบี้ยเลี้ยง)
    allowance_required = {
        "ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo", 
        "รายงานการเดินทาง", 
        "กำหนดการ", 
        "แบบฟอร์มการคำนวณเบี้ยเลี้ยง"
    }
    if allowance_required.issubset(found_classes):
        return {"claim_category": "ค่าเบี้ยเลี้ยง", "missing_documents": [], "status": "COMPLETE"}

    # Check 4: International Phone (ค่าโทรศัพท์เดินทางต่างประเทศ)
    phone_required = {
        "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด", 
        "รายงานการเดินทาง"
    }
    if phone_required.issubset(found_classes) and "Phone" in receipt_types:
         return {"claim_category": "ค่าโทรศัพท์เดินทางต่างประเทศ", "missing_documents": [], "status": "COMPLETE"}

    # Check 5: Surface Transport Group (Train, Bus, Taxi)
    # They all share the exact same required document checklist!
    transport_required = {
        "ใบเสร็จรับเงิน/ใบกำกับภาษี หรือ บิลเงินสด",
        "ใบอนุมัติปฏิบัติงานนอกสถานที่ในระบบ empeo",
        "รายงานการเดินทาง",
        "กำหนดการ"
    }

    if transport_required.issubset(found_classes):
        # We must rely on the VLM's extraction of the receipt_type to differentiate
        if "Train" in receipt_types:
            return {"claim_category": "ค่ารถไฟ", "missing_documents": [], "status": "COMPLETE"}
        elif "Taxi" in receipt_types:
            return {"claim_category": "ค่ายานพาหนะสาธารณะ Taxi", "missing_documents": [], "status": "COMPLETE"}
        elif "Bus" in receipt_types:
            return {"claim_category": "ค่ายานพาหนะโดยสารประจำทาง", "missing_documents": [], "status": "COMPLETE"}
        else:
            # Fallback if VLM couldn't read the receipt type but we have the transport docs
            return {
                "claim_category": "Unknown Surface Transport", 
                "missing_documents": [], 
                "status": "REQUIRES_MANUAL_REVIEW",
                "message": "Found transport documents but could not determine if Train, Bus, or Taxi from the receipt."
            }


    # If we reach here, the claim is incomplete based on the matrix
    return {
        "claim_category": "Incomplete or Unmatched",
        "missing_documents": ["Unable to determine missing docs due to unmatched base cluster."],
        "status": "INCOMPLETE",
        "found_documents": list(found_classes)
    }
