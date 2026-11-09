"""Tracker workbook import/export and the downloadable Excel template.

Sheet and column names match the Strategic Opportunities Tracker used by the MVP, so
existing workbooks load unchanged. Every row is normalised through the ontology.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import db, ontology

# sheet -> (table, [(header, field, vocab scheme or type, width, help)])
SHEETS: dict[str, tuple[str, list[tuple[str, str, str | None, int, str]]]] = {
    "Opportunities": ("opportunities", [
        ("Opportunity ID", "id", "id", 14, "Unique, e.g. OPP-021. Required."),
        ("Opportunity / Engagement", "name", None, 40, "Short descriptive title. Required."),
        ("Country", "country", "Country", 16, "Country of the counterparty / deployment."),
        ("Domain", "domain", "Domain", 12, "Security, Defense, Urban, Financial, Energy."),
        ("Customer Segment", "segment", "Segment", 14, "Government or Enterprise."),
        ("Counterparty", "counterparty", None, 32, "Client, partner or authority."),
        ("Opportunity Type", "type", "OpportunityType", 20, ""),
        ("Executive Sponsor", "sponsor", None, 24, "C-suite sponsor."),
        ("Executional Owner", "owner", None, 24, "Accountable lead."),
        ("Strategic Priority (1-5)", "priority", "int15", 12, "5 Critical … 1 Peripheral."),
        ("Commercial Potential (1-5)", "commercial", "int15", 12, "5 = AED 250m+, 4 = 100–249m, 3 = 25–99m, 2 = 5–24m, 1 = <5m."),
        ("Estimated Value (AED)", "value", "number", 18, "Indicative contract value in AED."),
        ("Status", "status", "Stage", 18, "Pipeline stage."),
        ("Outlook", "outlook", "Outlook", 11, ""),
        ("Outlook Rationale", "rationale", None, 36, ""),
        ("Latest Development", "latest", None, 40, ""),
        ("Last Engagement", "last_engagement", "date", 13, ""),
        ("Next Milestone", "milestone", None, 28, ""),
        ("Milestone Date", "milestone_date", "date", 13, ""),
        ("Next Action", "next_action", None, 36, ""),
        ("Action Owner", "action_owner", None, 22, ""),
        ("Intervention Required", "intervention", "YesNo", 12, "Yes if executive intervention is needed."),
        ("Announcement Potential", "announce", "AnnouncementPotential", 14, ""),
        ("Target Announcement", "target_announcement", "date", 13, ""),
        ("Sensitivity", "sensitivity", "Sensitivity", 13, ""),
        ("Last Verified", "verified", "date", 13, "Date the record was last confirmed."),
        ("Source / Reference", "source", None, 22, ""),
        ("Deployment Site", "site", None, 28, "Optional: site / zone name for the map."),
        ("Latitude", "lat", "number", 11, "Optional WGS84. Country centre used if blank."),
        ("Longitude", "lon", "number", 11, "Optional WGS84."),
        ("Competitors", "competitors", "number", 11, "Number of competitors identified."),
        ("SharePoint Folder URL", "sharepoint_url", None, 30, "Optional: document folder for this opportunity."),
        ("Teams Channel URL", "teams_web_url", None, 30, "Optional: filled automatically when a channel is created."),
    ]),
    "Engagement Log": ("engagements", [
        ("Engagement ID", "id", "id", 13, "Unique, e.g. ENG-101. Required."),
        ("Opportunity ID", "opp", "oppref", 14, "Must match an Opportunity ID."),
        ("Engagement Date", "date", "date", 13, ""),
        ("Engagement Type", "type", "EngagementType", 18, ""),
        ("External Participants", "external", None, 28, ""),
        ("Presight Participants", "internal", None, 28, ""),
        ("Summary / Outcome", "summary", None, 50, "Feeds sentiment in the win-probability model."),
        ("Commitments Made", "commitments", None, 32, ""),
        ("Follow-up Action", "follow_up", None, 30, ""),
        ("Action Owner", "owner", None, 22, ""),
        ("Due Date", "due", "date", 13, ""),
    ]),
    "Actions & Milestones": ("actions", [
        ("Action ID", "id", "id", 12, "Unique, e.g. ACT-101. Required."),
        ("Opportunity ID", "opp", "oppref", 14, ""),
        ("Action / Milestone", "title", None, 40, ""),
        ("Category", "category", "Category", 16, ""),
        ("Accountable Owner", "owner", None, 24, ""),
        ("Due Date", "due", "date", 13, ""),
        ("Status", "status", "ActionStatus", 14, "Blocked actions lower win probability."),
        ("Priority", "priority", "ActionPriority", 11, ""),
        ("Dependency / Blocker", "blocker", None, 32, ""),
        ("Escalation Required", "escalate", "YesNo", 12, ""),
        ("Latest Update", "update_note", None, 36, ""),
    ]),
    "Announcements": ("announcements", [
        ("Announcement ID", "id", "id", 14, "Unique, e.g. ANN-101. Required."),
        ("Opportunity ID", "opp", "oppref", 14, ""),
        ("Proposed Announcement", "title", None, 40, ""),
        ("Announcement Type", "type", "AnnouncementType", 18, ""),
        ("Target Date", "target", "date", 13, ""),
        ("Event / Platform", "event", None, 24, ""),
        ("Communications Lead", "lead", None, 22, ""),
        ("Readiness", "readiness", "Readiness", 18, ""),
        ("Legal Approval", "legal", "ApprovalState", 13, ""),
        ("IR / Disclosure Review", "ir", "ApprovalState", 13, ""),
        ("Counterparty Approval", "counterparty", "ApprovalState", 13, ""),
        ("Public Disclosure Permitted", "disclose", "YesNo", 13, ""),
    ]),
}
EXTRA_LISTS = {
    "EngagementType": ["Meeting", "Call", "Email", "Workshop", "Event", "Executive Engagement", "Site Visit"],
    "Category": ["Commercial", "Technical", "Legal", "Executive", "Communications", "Delivery"],
    "ActionPriority": ["Critical", "High", "Normal", "Low"],
    "AnnouncementType": ["Contract Award", "Partnership", "JV Launch", "MoU Signing", "Milestone", "Product Launch"],
}
CENTROIDS = {"UAE": (24.45, 54.38), "Saudi Arabia": (24.71, 46.68), "Oman": (23.59, 58.41), "Bahrain": (26.23, 50.59),
             "Egypt": (30.04, 31.24), "Morocco": (34.02, -6.84), "Jordan": (31.95, 35.93), "Kazakhstan": (51.17, 71.45),
             "Uzbekistan": (41.30, 69.24), "Azerbaijan": (40.41, 49.87), "Georgia": (41.72, 44.79), "Albania": (41.33, 19.82),
             "Montenegro": (42.43, 19.26), "Serbia": (44.79, 20.45), "Dominican Republic": (18.49, -69.93),
             "Indonesia": (-6.21, 106.85), "Kenya": (-1.29, 36.82)}

NAVY = "0D1A22"
TEAL = "0A6E7C"
THIN = Side(style="thin", color="D9E1E4")


def list_values(scheme: str) -> list[str]:
    if scheme == "Country":
        return list(ontology.COUNTRIES)
    if scheme in EXTRA_LISTS:
        return EXTRA_LISTS[scheme]
    return list(ontology.VOCAB.get(scheme, {}))


def build_template(with_examples: bool = True, data: dict[str, list[dict]] | None = None) -> bytes:
    """Excel tracker template: instructions, the four tracker sheets with dropdown validation, and a Lists sheet.

    With `data`, the same workbook is filled with records (used for export / round-trip).
    """
    wb = Workbook()
    ins = wb.active
    ins.title = "Instructions"
    ins.sheet_view.showGridLines = False
    ins.column_dimensions["A"].width = 3
    ins.column_dimensions["B"].width = 28
    ins.column_dimensions["C"].width = 90
    ins["B2"] = "Precast Strategic Opportunities Tracker"
    ins["B2"].font = Font(name="Calibri", size=18, bold=True, color=NAVY)
    ins["B3"] = "Predict. Forecast. Precast.  ·  Template v" + ontology.VERSION
    ins["B3"].font = Font(size=10, color=TEAL, italic=True)
    rows = [
        ("How to use", "Fill one row per record in each sheet. Keep the header row unchanged. Load the file with “Load tracker” in Precast (Data & Integrations)."),
        ("Required fields", "Every sheet needs its ID column. Engagements, actions and announcements also need an Opportunity ID that exists in Opportunities."),
        ("Dropdowns", "Coloured columns have dropdown lists from the Precast ontology. Arabic labels and common synonyms are also accepted on import (e.g. “KSA”, “السعودية”)."),
        ("Dates", "Use real Excel dates (dd-mmm-yyyy). Text dates in YYYY-MM-DD also work."),
        ("Values", "Estimated Value is in AED, as a plain number (e.g. 185000000)."),
        ("Win probability", "Precast calculates win probability, risk-weighted expected value and expected close itself. Do not add them here; the Engagement Log, actions and outlook drive them."),
        ("Import modes", "Merge (default) updates matching IDs and adds new ones. Replace clears the register first."),
        ("Confidentiality", "The file is processed inside your Precast deployment. Mark each opportunity’s Sensitivity correctly."),
    ]
    for i, (k, v) in enumerate(rows, start=5):
        ins.cell(i, 2, k).font = Font(bold=True, color=NAVY)
        c = ins.cell(i, 3, v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ins.row_dimensions[i].height = 32

    lists = wb.create_sheet("Lists")
    schemes: list[str] = []
    for _, (_, cols) in SHEETS.items():
        for _, _, s, _, _ in cols:
            if s and s not in ("id", "date", "number", "int15", "oppref") and s not in schemes:
                schemes.append(s)
    ranges = {}
    for ci, s in enumerate(schemes, start=1):
        vals = list_values(s)
        lists.cell(1, ci, s).font = Font(bold=True, color="FFFFFF")
        lists.cell(1, ci).fill = PatternFill("solid", fgColor=NAVY)
        for ri, v in enumerate(vals, start=2):
            lists.cell(ri, ci, v)
        col = get_column_letter(ci)
        ranges[s] = f"Lists!${col}$2:${col}${len(vals) + 1}"
        lists.column_dimensions[col].width = max(14, max(len(v) for v in vals) + 2)

    hdr_fill = PatternFill("solid", fgColor=NAVY)
    dd_fill = PatternFill("solid", fgColor="D6ECEF")
    examples = {
        "Opportunities": [["OPP-101", "Example: City-wide video analytics", "Saudi Arabia", "Security", "Government", "Example: Municipal Authority",
                           "Commercial Contract", "Chief Operating Officer", "Head of Public Safety", 4, 4, 150000000, "Proposal", "Positive",
                           "Pilot results strong", "Proposal requested after pilot", date.today(), "Proposal submission", date.today(),
                           "Submit proposal", "Head of Public Safety", "No", "Under Consideration", None, "Confidential", date.today(),
                           "Example row – delete", "Riyadh command centre", 24.7136, 46.6753, 2, "", ""]],
        "Engagement Log": [["ENG-101", "OPP-101", date.today(), "Meeting", "Authority CIO", "Account team",
                            "Pilot review; client supportive and keen to scale.", "Share proposal in 2 weeks", "Draft proposal",
                            "Head of Public Safety", date.today()]],
        "Actions & Milestones": [["ACT-101", "OPP-101", "Proposal submission", "Commercial", "Head of Public Safety", date.today(),
                                  "In Progress", "High", "", "No", ""]],
        "Announcements": [["ANN-101", "OPP-101", "Example: City-wide analytics award", "Contract Award", date.today(), "Press release",
                           "Communications Lead", "Planning", "Pending", "Pending", "Pending", "No"]],
    }
    for sheet, (table, cols) in SHEETS.items():
        ws = wb.create_sheet(sheet, index=len(wb.sheetnames) - 1)
        for ci, (h, field, scheme, width, help_) in enumerate(cols, start=1):
            c = ws.cell(1, ci, h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = hdr_fill
            c.alignment = Alignment(wrap_text=True, vertical="center")
            c.border = Border(bottom=THIN)
            if help_:
                c.comment = Comment(help_, "Precast")
            ws.column_dimensions[get_column_letter(ci)].width = width
            col = get_column_letter(ci)
            rng = f"{col}2:{col}2000"
            if scheme in ranges:
                dv = DataValidation(type="list", formula1=f"={ranges[scheme]}", allow_blank=True, showErrorMessage=False)
                dv.promptTitle, dv.prompt = h[:32], (help_ or "Pick from the list")[:250]
                ws.add_data_validation(dv)
                dv.add(rng)
                ws.cell(1, ci).fill = PatternFill("solid", fgColor=TEAL)
            elif scheme == "int15":
                dv = DataValidation(type="whole", operator="between", formula1="1", formula2="5", allow_blank=True)
                dv.error, dv.errorTitle = "Enter a whole number from 1 to 5", "Score 1–5"
                ws.add_data_validation(dv)
                dv.add(rng)
            elif scheme == "date":
                for r in range(2, 302):
                    ws.cell(r, ci).number_format = "dd-mmm-yyyy"
            elif scheme == "number" and field == "value":
                for r in range(2, 302):
                    ws.cell(r, ci).number_format = '#,##0'
            elif scheme == "oppref" and sheet != "Opportunities":
                dv = DataValidation(type="list", formula1="=Opportunities!$A$2:$A$2000", allow_blank=True, showErrorMessage=False)
                ws.add_data_validation(dv)
                dv.add(rng)
        ws.freeze_panes = "C2" if sheet == "Opportunities" else "B2"
        ws.row_dimensions[1].height = 34
        ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}1"
        if data is not None:
            for ri, rec in enumerate(data.get(table, []), start=2):
                for ci, (_, field, scheme, _, _) in enumerate(cols, start=1):
                    v = rec.get(field)
                    if scheme == "date" and v:
                        try:
                            v = date.fromisoformat(str(v)[:10])
                        except ValueError:
                            pass
                    ws.cell(ri, ci, v)
        elif with_examples:
            for ri, row in enumerate(examples[sheet], start=2):
                for ci, v in enumerate(row, start=1):
                    c = ws.cell(ri, ci, v)
                    c.font = Font(italic=True, color="56666F")
                    c.fill = dd_fill if False else PatternFill(None)
    wb.move_sheet("Lists", offset=len(wb.sheetnames))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_workbook() -> bytes:
    data = {t: [r for r in db.all_rows(t) if not str(r.get("id", "")).startswith("HIS-")]
            for t in ("opportunities", "engagements", "actions", "announcements")}
    return build_template(with_examples=False, data=data)


def _cell(v: Any, scheme: str | None) -> Any:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if scheme == "date":
        if isinstance(v, (datetime, date)):
            return (v.date() if isinstance(v, datetime) else v).isoformat()
        if isinstance(v, (int, float)):
            from datetime import timedelta
            return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()
        s = str(v).strip()
        for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%d %b %Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(s[:11], fmt).date().isoformat()
            except ValueError:
                continue
        return None
    if scheme in ("number", "int15"):
        if isinstance(v, (int, float)):
            return v
        try:
            return float(str(v).replace(",", "").replace("AED", "").strip())
        except ValueError:
            return None
    return str(v).strip() if isinstance(v, str) else v


def import_workbook(content: bytes, mode: str = "merge") -> dict:
    try:
        wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Not a readable .xlsx workbook ({type(e).__name__}).") from e
    names = {n.strip().lower(): n for n in wb.sheetnames}
    if "opportunities" not in names:
        raise ValueError("This workbook has no “Opportunities” sheet. Download the Precast template to see the expected layout.")
    if mode == "replace":
        with db.tx() as c:
            for t in ("discussions", "announcements", "actions", "engagements"):
                c.execute(f"DELETE FROM {t}")
            c.execute("DELETE FROM opportunities WHERE id NOT LIKE 'HIS-%'")
    result = {"mode": mode, "counts": {}, "warnings": [], "skipped": 0}
    known = {o["id"] for o in db.all_rows("opportunities")}
    for sheet, (table, cols) in SHEETS.items():
        key = sheet.lower()
        if key not in names:
            continue
        ws = wb[names[key]]
        it = ws.iter_rows(values_only=True)
        try:
            header = [str(h).strip().lower() if h is not None else "" for h in next(it)]
        except StopIteration:
            continue
        pos = {}
        for h, field, scheme, _, _ in cols:
            if h.lower() in header:
                pos[field] = (header.index(h.lower()), scheme)
        n = 0
        for r, row in enumerate(it, start=2):
            if not row or all(v is None or str(v).strip() == "" for v in row):
                continue
            rec = {f: _cell(row[i] if i < len(row) else None, s) for f, (i, s) in pos.items()}
            if str(rec.get("source") or "").lower().startswith("example row"):
                continue
            if not rec.get("id"):
                result["warnings"].append(f"{sheet} row {r}: no ID, skipped")
                result["skipped"] += 1
                continue
            rec["id"] = str(rec["id"]).strip()
            if table != "opportunities" and rec.get("opp") not in known:
                result["warnings"].append(f"{sheet} {rec['id']}: Opportunity ID '{rec.get('opp')}' not found, skipped")
                result["skipped"] += 1
                continue
            try:
                clean, warns = ontology.validate(table, rec)
            except ValueError as e:
                result["warnings"].append(f"{sheet} row {r}: {e}")
                result["skipped"] += 1
                continue
            result["warnings"].extend(warns)
            if table == "opportunities":
                for k in ("priority", "commercial", "competitors"):
                    if clean.get(k) is not None:
                        clean[k] = int(clean[k])
                if (clean.get("lat") is None or clean.get("lon") is None) and clean.get("country") in CENTROIDS:
                    clean["lat"], clean["lon"] = CENTROIDS[clean["country"]]
                clean.setdefault("created", date.today().isoformat())
                known.add(clean["id"])
            clean = {k: v for k, v in clean.items() if v is not None}
            if table == "actions":
                clean.setdefault("created", date.today().isoformat())
            db.upsert(table, clean)
            n += 1
        result["counts"][table] = n
    if not result["counts"].get("opportunities") and mode == "replace":
        result["warnings"].append("The Opportunities sheet had no rows; the register is now empty.")
    result["warnings"] = result["warnings"][:200]
    return result
