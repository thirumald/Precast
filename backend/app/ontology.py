"""Precast ontology: the shared semantic model of the strategic pipeline.

One definition drives four things:
  * ingestion validation (controlled vocabularies, required properties, ranges),
  * the bilingual natural-language parser (labels and synonyms in English and Arabic),
  * LLM grounding (a compact schema summary is placed in prompts),
  * the knowledge graph (instance data projected onto classes and relations).

Exports as OWL/Turtle and JSON-LD so it can be loaded into Protégé, a triple store or a
data catalogue without change.
"""
from __future__ import annotations

from typing import Any

NS = "https://precast.presight.ai/ontology#"
PREFIX = "pc"
VERSION = "1.0.0"

# ---------------------------------------------------------------- classes
CLASSES: dict[str, dict[str, Any]] = {
    "Opportunity": {"label": {"en": "Opportunity", "ar": "فرصة"}, "parent": None,
                    "comment": "A strategic commercial pursuit tracked by the executive team."},
    "Organisation": {"label": {"en": "Organisation", "ar": "جهة"}, "parent": None,
                     "comment": "Any legal entity."},
    "Counterparty": {"label": {"en": "Counterparty", "ar": "الطرف المقابل"}, "parent": "Organisation",
                     "comment": "The client, partner or authority on the other side of an opportunity."},
    "Person": {"label": {"en": "Person / Role", "ar": "شخص / دور"}, "parent": None,
               "comment": "An accountable role, e.g. Executive Sponsor or Executional Owner."},
    "ExecutiveSponsor": {"label": {"en": "Executive Sponsor", "ar": "الراعي التنفيذي"}, "parent": "Person", "comment": ""},
    "ExecutionalOwner": {"label": {"en": "Executional Owner", "ar": "المسؤول التنفيذي"}, "parent": "Person", "comment": ""},
    "Country": {"label": {"en": "Country", "ar": "دولة"}, "parent": "Location", "comment": ""},
    "Region": {"label": {"en": "Region", "ar": "منطقة"}, "parent": "Location", "comment": ""},
    "Location": {"label": {"en": "Location", "ar": "موقع"}, "parent": None, "comment": ""},
    "Site": {"label": {"en": "Deployment Site", "ar": "موقع النشر"}, "parent": "Location",
             "comment": "A physical deployment zone: radar site, smart-city perimeter, command centre."},
    "Domain": {"label": {"en": "Business Domain", "ar": "المجال"}, "parent": "Concept", "comment": ""},
    "Stage": {"label": {"en": "Pipeline Stage", "ar": "المرحلة"}, "parent": "Concept", "comment": ""},
    "Outlook": {"label": {"en": "Outlook", "ar": "التوقع"}, "parent": "Concept", "comment": ""},
    "Concept": {"label": {"en": "Concept", "ar": "مفهوم"}, "parent": None, "comment": "Controlled vocabulary term."},
    "Engagement": {"label": {"en": "Engagement", "ar": "تواصل"}, "parent": "Event",
                   "comment": "A recorded interaction with the counterparty (Engagement Log)."},
    "Action": {"label": {"en": "Action / Milestone", "ar": "إجراء / مرحلة"}, "parent": "Event", "comment": ""},
    "Announcement": {"label": {"en": "Announcement", "ar": "إعلان"}, "parent": "Event", "comment": ""},
    "Approval": {"label": {"en": "Clearance Approval", "ar": "موافقة"}, "parent": None,
                 "comment": "Legal, IR or counterparty clearance on an announcement."},
    "Event": {"label": {"en": "Event", "ar": "حدث"}, "parent": None, "comment": ""},
    "Prediction": {"label": {"en": "Prediction", "ar": "تنبؤ"}, "parent": None,
                   "comment": "Model output: win probability, expected value, expected close."},
    "ScoreFactor": {"label": {"en": "Score Factor", "ar": "عامل التقييم"}, "parent": None,
                    "comment": "An explainable driver that moved a prediction."},
}

# ---------------------------------------------------------------- relations (object properties)
RELATIONS: dict[str, dict[str, Any]] = {
    "hasCounterparty": {"domain": "Opportunity", "range": "Counterparty", "label": {"en": "has counterparty", "ar": "طرفها"}},
    "locatedIn": {"domain": "Opportunity", "range": "Country", "label": {"en": "located in", "ar": "تقع في"}},
    "deployedAt": {"domain": "Opportunity", "range": "Site", "label": {"en": "deployed at", "ar": "تُنشر في"}},
    "siteIn": {"domain": "Site", "range": "Country", "label": {"en": "site in", "ar": "موقع في"}},
    "partOfRegion": {"domain": "Country", "range": "Region", "label": {"en": "part of region", "ar": "جزء من منطقة"}},
    "inDomain": {"domain": "Opportunity", "range": "Domain", "label": {"en": "in domain", "ar": "في مجال"}},
    "atStage": {"domain": "Opportunity", "range": "Stage", "label": {"en": "at stage", "ar": "في مرحلة"}},
    "hasOutlook": {"domain": "Opportunity", "range": "Outlook", "label": {"en": "has outlook", "ar": "توقعها"}},
    "sponsoredBy": {"domain": "Opportunity", "range": "ExecutiveSponsor", "label": {"en": "sponsored by", "ar": "برعاية"}},
    "ownedBy": {"domain": "Opportunity", "range": "ExecutionalOwner", "label": {"en": "owned by", "ar": "يملكها"}},
    "hasEngagement": {"domain": "Opportunity", "range": "Engagement", "label": {"en": "has engagement", "ar": "لديها تواصل"}},
    "hasAction": {"domain": "Opportunity", "range": "Action", "label": {"en": "has action", "ar": "لديها إجراء"}},
    "hasAnnouncement": {"domain": "Opportunity", "range": "Announcement", "label": {"en": "has announcement", "ar": "لديها إعلان"}},
    "accountable": {"domain": "Action", "range": "Person", "label": {"en": "accountable owner", "ar": "المسؤول"}},
    "requiresApproval": {"domain": "Announcement", "range": "Approval", "label": {"en": "requires approval", "ar": "يتطلب موافقة"}},
    "hasPrediction": {"domain": "Opportunity", "range": "Prediction", "label": {"en": "has prediction", "ar": "لديها تنبؤ"}},
    "explainedBy": {"domain": "Prediction", "range": "ScoreFactor", "label": {"en": "explained by", "ar": "مفسر بـ"}},
    "precedes": {"domain": "Stage", "range": "Stage", "label": {"en": "precedes", "ar": "تسبق"}, "transitive": True},
}

# ---------------------------------------------------------------- data properties
# name: (class, xsd type, required, description)
PROPERTIES: dict[str, tuple[str, str, bool, str]] = {
    "id": ("Opportunity", "string", True, "Stable identifier, e.g. OPP-001"),
    "name": ("Opportunity", "string", True, "Opportunity / engagement title"),
    "value": ("Opportunity", "decimal", False, "Estimated value in AED"),
    "priority": ("Opportunity", "integer[1..5]", False, "Strategic priority: 5 critical … 1 peripheral"),
    "commercial": ("Opportunity", "integer[1..5]", False, "Manual commercial potential band"),
    "segment": ("Opportunity", "enum:Segment", False, "Government or Enterprise"),
    "type": ("Opportunity", "enum:OpportunityType", False, "Commercial nature of the pursuit"),
    "intervention": ("Opportunity", "enum:YesNo", False, "Executive intervention required"),
    "announce": ("Opportunity", "enum:AnnouncementPotential", False, "Announcement potential"),
    "sensitivity": ("Opportunity", "enum:Sensitivity", False, "Information classification"),
    "milestone_date": ("Opportunity", "date", False, "Next milestone date"),
    "verified": ("Opportunity", "date", False, "Last verified"),
    "lat": ("Site", "decimal[-90..90]", False, "Latitude (WGS84)"),
    "lon": ("Site", "decimal[-180..180]", False, "Longitude (WGS84)"),
    "competitors": ("Opportunity", "integer[0..]", False, "Number of competitors identified"),
    "date": ("Engagement", "date", True, "Engagement date"),
    "summary": ("Engagement", "string", False, "Summary / outcome"),
    "due": ("Action", "date", False, "Due date"),
    "status": ("Action", "enum:ActionStatus", False, "Action status"),
    "escalate": ("Action", "enum:YesNo", False, "Escalation required"),
    "readiness": ("Announcement", "enum:Readiness", False, "Announcement readiness"),
    "legal": ("Approval", "enum:ApprovalState", False, "Legal approval"),
    "ir": ("Approval", "enum:ApprovalState", False, "IR / disclosure review"),
    "p": ("Prediction", "decimal[0..1]", False, "Win probability"),
    "ev": ("Prediction", "decimal", False, "Risk-weighted expected value (AED)"),
}

# ---------------------------------------------------------------- controlled vocabularies
# term -> {ar label, synonyms (lower-case, en + ar)}
VOCAB: dict[str, dict[str, dict[str, Any]]] = {
    "Domain": {
        "Security": {"ar": "الأمن", "syn": ["security", "public safety", "safe city", "cyber", "surveillance", "أمن", "الأمن", "أمنية", "الأمنية", "السلامة العامة"]},
        "Defense": {"ar": "الدفاع", "syn": ["defense", "defence", "military", "armed forces", "border", "دفاع", "الدفاع", "الدفاعية", "عسكري"]},
        "Urban": {"ar": "الحلول الحضرية", "syn": ["urban", "smart city", "city", "transport", "traffic", "mobility", "حضري", "المدن", "المدينة الذكية", "النقل"]},
        "Financial": {"ar": "المالية", "syn": ["financial", "finance", "banking", "bank", "fintech", "مالي", "المالية", "مصرفي"]},
        "Energy": {"ar": "الطاقة", "syn": ["energy", "grid", "power", "oil", "gas", "renewable", "طاقة", "الطاقة", "كهرباء"]},
    },
    "Stage": {
        "Exploratory": {"ar": "استكشافية", "syn": ["exploratory", "early", "lead", "استكشافية"], "order": 1, "p": 0.10},
        "Active Engagement": {"ar": "تواصل نشط", "syn": ["active engagement", "engaged", "qualification", "تواصل نشط"], "order": 2, "p": 0.20},
        "Proposal": {"ar": "عرض", "syn": ["proposal", "bid", "tender", "rfp", "عرض", "مناقصة"], "order": 3, "p": 0.35},
        "Negotiation": {"ar": "تفاوض", "syn": ["negotiation", "negotiating", "commercials", "تفاوض"], "order": 4, "p": 0.55},
        "Agreement": {"ar": "اتفاق", "syn": ["agreement", "contracting", "signature", "اتفاق", "توقيع"], "order": 5, "p": 0.80},
        "Execution": {"ar": "تنفيذ", "syn": ["execution", "delivery", "implementation", "تنفيذ"], "order": 6, "p": 0.95},
        "Closed Won": {"ar": "مكسوبة", "syn": ["closed won", "won", "مكسوبة", "فزنا"], "order": 7, "terminal": True},
        "Closed Lost": {"ar": "خاسرة", "syn": ["closed lost", "lost", "خاسرة", "خسرنا"], "order": 7, "terminal": True},
        "On Hold": {"ar": "معلقة", "syn": ["on hold", "paused", "معلقة"], "order": 0, "terminal": False},
    },
    "Outlook": {
        "Positive": {"ar": "إيجابي", "syn": ["positive", "good", "إيجابي"]},
        "Neutral": {"ar": "محايد", "syn": ["neutral", "محايد"]},
        "Negative": {"ar": "سلبي", "syn": ["negative", "bad", "سلبي"]},
    },
    "Segment": {"Government": {"ar": "حكومي", "syn": ["government", "public sector", "gov", "حكومي"]},
                "Enterprise": {"ar": "مؤسسات", "syn": ["enterprise", "private", "corporate", "مؤسسات"]}},
    "OpportunityType": {t: {"ar": a, "syn": [t.lower()]} for t, a in [
        ("Commercial Contract", "عقد تجاري"), ("Strategic Partnership", "شراكة استراتيجية"), ("Joint Venture", "مشروع مشترك"),
        ("MoU", "مذكرة تفاهم"), ("Market Access", "دخول السوق"), ("Strategic Engagement", "تواصل استراتيجي")]},
    "ActionStatus": {s: {"ar": a, "syn": [s.lower()]} for s, a in [
        ("Not Started", "لم يبدأ"), ("In Progress", "قيد التنفيذ"), ("Blocked", "متعثر"), ("Completed", "مكتمل"), ("Cancelled", "ملغى")]},
    "Readiness": {s: {"ar": a, "syn": [s.lower()]} for s, a in [
        ("Planning", "تخطيط"), ("Pending Approvals", "بانتظار الموافقات"), ("Approved", "معتمد"), ("Deferred", "مؤجل"),
        ("Announced", "أُعلن"), ("Cancelled", "ملغى")]},
    "ApprovalState": {s: {"ar": a, "syn": [s.lower()]} for s, a in [
        ("Pending", "قيد الانتظار"), ("Approved", "معتمد"), ("Rejected", "مرفوض"), ("Not Required", "غير مطلوب")]},
    "YesNo": {"Yes": {"ar": "نعم", "syn": ["yes", "y", "true", "نعم"]}, "No": {"ar": "لا", "syn": ["no", "n", "false", "لا"]}},
    "AnnouncementPotential": {"Yes": {"ar": "نعم", "syn": ["yes"]}, "No": {"ar": "لا", "syn": ["no"]},
                              "Under Consideration": {"ar": "قيد الدراسة", "syn": ["under consideration", "maybe", "tbc"]}},
    "Sensitivity": {s: {"ar": a, "syn": [s.lower()]} for s, a in [
        ("Public", "عام"), ("Internal", "داخلي"), ("Confidential", "سري"), ("Restricted", "مقيد")]},
}

COUNTRIES: dict[str, dict[str, Any]] = {
    "UAE": {"ar": "الإمارات", "region": "GCC", "syn": ["uae", "united arab emirates", "emirates", "الإمارات", "الامارات", "abu dhabi", "dubai"]},
    "Saudi Arabia": {"ar": "السعودية", "region": "GCC", "syn": ["saudi arabia", "saudi", "ksa", "السعودية", "المملكة العربية السعودية", "riyadh"]},
    "Oman": {"ar": "عُمان", "region": "GCC", "syn": ["oman", "عمان", "عُمان"]},
    "Bahrain": {"ar": "البحرين", "region": "GCC", "syn": ["bahrain", "البحرين"]},
    "Egypt": {"ar": "مصر", "region": "North Africa", "syn": ["egypt", "مصر"]},
    "Morocco": {"ar": "المغرب", "region": "North Africa", "syn": ["morocco", "المغرب"]},
    "Jordan": {"ar": "الأردن", "region": "Levant", "syn": ["jordan", "الأردن"]},
    "Kazakhstan": {"ar": "كازاخستان", "region": "Central Asia", "syn": ["kazakhstan", "كازاخستان"]},
    "Uzbekistan": {"ar": "أوزبكستان", "region": "Central Asia", "syn": ["uzbekistan", "أوزبكستان"]},
    "Azerbaijan": {"ar": "أذربيجان", "region": "Caucasus", "syn": ["azerbaijan", "أذربيجان"]},
    "Georgia": {"ar": "جورجيا", "region": "Caucasus", "syn": ["georgia", "جورجيا"]},
    "Albania": {"ar": "ألبانيا", "region": "Balkans", "syn": ["albania", "ألبانيا"]},
    "Montenegro": {"ar": "الجبل الأسود", "region": "Balkans", "syn": ["montenegro", "الجبل الأسود"]},
    "Serbia": {"ar": "صربيا", "region": "Balkans", "syn": ["serbia", "صربيا"]},
    "Dominican Republic": {"ar": "الدومينيكان", "region": "Caribbean", "syn": ["dominican republic", "الدومينيكان"]},
    "Indonesia": {"ar": "إندونيسيا", "region": "South-East Asia", "syn": ["indonesia", "إندونيسيا"]},
    "Kenya": {"ar": "كينيا", "region": "East Africa", "syn": ["kenya", "كينيا"]},
}

# Which record fields are governed by which vocabulary, per table.
FIELD_VOCAB = {
    "opportunities": {"domain": "Domain", "status": "Stage", "outlook": "Outlook", "segment": "Segment", "type": "OpportunityType",
                      "intervention": "YesNo", "announce": "AnnouncementPotential", "sensitivity": "Sensitivity"},
    "actions": {"status": "ActionStatus", "escalate": "YesNo"},
    "announcements": {"readiness": "Readiness", "legal": "ApprovalState", "ir": "ApprovalState", "counterparty": "ApprovalState"},
}
REQUIRED = {"opportunities": ["id", "name"], "engagements": ["id", "opp"], "actions": ["id", "opp"], "announcements": ["id", "opp"]}
RANGES = {"priority": (1, 5), "commercial": (1, 5), "lat": (-90, 90), "lon": (-180, 180), "value": (0, None), "competitors": (0, None)}


# ---------------------------------------------------------------- lookup helpers
def _index() -> dict[str, dict[str, str]]:
    idx: dict[str, dict[str, str]] = {}
    for scheme, terms in VOCAB.items():
        m = idx.setdefault(scheme, {})
        for term, meta in terms.items():
            m[term.lower()] = term
            m[meta["ar"].lower()] = term
            for s in meta.get("syn", []):
                m[s.lower()] = term
    m = idx.setdefault("Country", {})
    for c, meta in COUNTRIES.items():
        m[c.lower()] = c
        m[meta["ar"]] = c
        for s in meta["syn"]:
            m[s.lower()] = c
    return idx


_IDX = _index()


def normalise(scheme: str, value: Any) -> str | None:
    """Map a raw value (any case, synonym or Arabic label) to the canonical vocabulary term."""
    if value is None or str(value).strip() == "":
        return None
    return _IDX.get(scheme, {}).get(str(value).strip().lower())


def synonyms(scheme: str) -> dict[str, str]:
    """synonym -> canonical term, longest first (so 'smart city' wins over 'city')."""
    return dict(sorted(_IDX.get(scheme, {}).items(), key=lambda kv: -len(kv[0])))


def region_of(country: str | None) -> str | None:
    return COUNTRIES.get(country or "", {}).get("region")


def stage_order() -> list[str]:
    return [s for s, m in sorted(VOCAB["Stage"].items(), key=lambda kv: kv[1]["order"]) if not m.get("terminal") and m["order"] > 0]


def validate(table: str, row: dict) -> tuple[dict, list[str]]:
    """Normalise a record against the ontology. Returns (clean_row, warnings). Raises on missing required fields."""
    clean = dict(row)
    warnings: list[str] = []
    for f in REQUIRED.get(table, []):
        if not clean.get(f):
            raise ValueError(f"{table}: missing required property '{f}'")
    for field, scheme in FIELD_VOCAB.get(table, {}).items():
        raw = clean.get(field)
        if raw in (None, ""):
            continue
        canon = normalise(scheme, raw)
        if canon:
            clean[field] = canon
        else:
            warnings.append(f"{clean.get('id')}: '{raw}' is not a known {scheme} term ({field})")
    if table == "opportunities" and clean.get("country"):
        c = normalise("Country", clean["country"])
        if c:
            clean["country"] = c
    for field, (lo, hi) in RANGES.items():
        v = clean.get(field)
        if v in (None, ""):
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            warnings.append(f"{clean.get('id')}: {field} '{clean[field]}' is not numeric")
            clean[field] = None
            continue
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            warnings.append(f"{clean.get('id')}: {field} {v} outside {lo}..{hi}")
            clean[field] = max(lo, min(v, hi)) if hi is not None else max(lo, v)
    return clean, warnings


def prompt_summary() -> str:
    """Compact schema for LLM grounding."""
    return (
        "ONTOLOGY: Opportunity -hasCounterparty-> Counterparty; -locatedIn-> Country -partOfRegion-> Region; "
        "-inDomain-> Domain{" + ", ".join(VOCAB["Domain"]) + "}; -atStage-> Stage{" + " > ".join(stage_order()) +
        ", Closed Won, Closed Lost, On Hold}; -hasOutlook-> Outlook{Positive, Neutral, Negative}; "
        "-sponsoredBy-> ExecutiveSponsor; -hasEngagement-> Engagement; -hasAction-> Action{status: "
        + ", ".join(VOCAB["ActionStatus"]) + "}; -hasAnnouncement-> Announcement -requiresApproval-> Approval{Legal, IR, Counterparty}; "
        "-hasPrediction-> Prediction{win probability p, expected value ev = value × p} -explainedBy-> ScoreFactor."
    )


# ---------------------------------------------------------------- serialisations
def as_dict() -> dict:
    return {"namespace": NS, "version": VERSION, "classes": CLASSES, "relations": RELATIONS,
            "properties": {k: {"class": c, "type": t, "required": r, "comment": d} for k, (c, t, r, d) in PROPERTIES.items()},
            "vocabularies": VOCAB, "countries": COUNTRIES}


def _lit(s: str, lang: str | None = None) -> str:
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"' + (f"@{lang}" if lang else "")


def _local(s: str) -> str:
    return "".join(w[:1].upper() + w[1:] for w in s.replace("/", " ").replace("-", " ").split())


def to_turtle() -> str:
    out = [f"@prefix {PREFIX}: <{NS}> .", "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
           "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .", "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
           "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .", "",
           f"<{NS.rstrip('#')}> a owl:Ontology ; rdfs:label \"Precast Strategic Pipeline Ontology\"@en ; owl:versionInfo {_lit(VERSION)} .", ""]
    for c, m in CLASSES.items():
        out.append(f"{PREFIX}:{c} a owl:Class ; rdfs:label {_lit(m['label']['en'], 'en')}, {_lit(m['label']['ar'], 'ar')}"
                   + (f" ; rdfs:subClassOf {PREFIX}:{m['parent']}" if m["parent"] else "")
                   + (f" ; rdfs:comment {_lit(m['comment'], 'en')}" if m["comment"] else "") + " .")
    out.append("")
    for r, m in RELATIONS.items():
        typ = "owl:ObjectProperty" + (", owl:TransitiveProperty" if m.get("transitive") else "")
        out.append(f"{PREFIX}:{r} a {typ} ; rdfs:domain {PREFIX}:{m['domain']} ; rdfs:range {PREFIX}:{m['range']} ; "
                   f"rdfs:label {_lit(m['label']['en'], 'en')}, {_lit(m['label']['ar'], 'ar')} .")
    out.append("")
    xsd = {"string": "xsd:string", "decimal": "xsd:decimal", "integer": "xsd:integer", "date": "xsd:date"}
    for p, (c, t, req, d) in PROPERTIES.items():
        base = t.split("[")[0]
        rng = xsd.get(base, f"{PREFIX}:{_local(t.split(':')[1])}Scheme" if base.startswith("enum") else "xsd:string")
        out.append(f"{PREFIX}:{p} a owl:DatatypeProperty ; rdfs:domain {PREFIX}:{c} ; rdfs:range {rng} ; rdfs:comment {_lit(d, 'en')} .")
    out.append("")
    for scheme, terms in VOCAB.items():
        sid = f"{PREFIX}:{scheme}Scheme"
        out.append(f"{sid} a skos:ConceptScheme ; rdfs:label {_lit(scheme, 'en')} .")
        for term, m in terms.items():
            alts = ", ".join(_lit(s) for s in m.get("syn", []) if s.lower() != term.lower())
            out.append(f"{PREFIX}:{scheme}_{_local(term)} a skos:Concept ; skos:inScheme {sid} ; skos:prefLabel {_lit(term, 'en')}, {_lit(m['ar'], 'ar')}"
                       + (f" ; skos:altLabel {alts}" if alts else "") + " .")
    stages = stage_order()
    for a, b in zip(stages, stages[1:]):
        out.append(f"{PREFIX}:Stage_{_local(a)} {PREFIX}:precedes {PREFIX}:Stage_{_local(b)} .")
    out.append("")
    for c, m in COUNTRIES.items():
        out.append(f"{PREFIX}:Country_{_local(c)} a {PREFIX}:Country ; skos:prefLabel {_lit(c, 'en')}, {_lit(m['ar'], 'ar')} ; "
                   f"{PREFIX}:partOfRegion {PREFIX}:Region_{_local(m['region'])} .")
    for r in sorted({m["region"] for m in COUNTRIES.values()}):
        out.append(f"{PREFIX}:Region_{_local(r)} a {PREFIX}:Region ; rdfs:label {_lit(r, 'en')} .")
    return "\n".join(out) + "\n"


def to_jsonld() -> dict:
    g: list[dict] = []
    for c, m in CLASSES.items():
        n = {"@id": f"{PREFIX}:{c}", "@type": "owl:Class",
             "rdfs:label": [{"@value": m["label"]["en"], "@language": "en"}, {"@value": m["label"]["ar"], "@language": "ar"}]}
        if m["parent"]:
            n["rdfs:subClassOf"] = {"@id": f"{PREFIX}:{m['parent']}"}
        g.append(n)
    for r, m in RELATIONS.items():
        g.append({"@id": f"{PREFIX}:{r}", "@type": "owl:ObjectProperty", "rdfs:domain": {"@id": f"{PREFIX}:{m['domain']}"},
                  "rdfs:range": {"@id": f"{PREFIX}:{m['range']}"}, "rdfs:label": m["label"]["en"]})
    for scheme, terms in VOCAB.items():
        for term, m in terms.items():
            g.append({"@id": f"{PREFIX}:{scheme}_{_local(term)}", "@type": "skos:Concept", "skos:inScheme": {"@id": f"{PREFIX}:{scheme}Scheme"},
                      "skos:prefLabel": [{"@value": term, "@language": "en"}, {"@value": m["ar"], "@language": "ar"}],
                      "skos:altLabel": m.get("syn", [])})
    return {"@context": {PREFIX: NS, "owl": "http://www.w3.org/2002/07/owl#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                         "skos": "http://www.w3.org/2004/02/skos/core#"}, "@graph": g}


# ---------------------------------------------------------------- knowledge graph
def knowledge_graph(snap, focus: str | None = None, include_events: bool = True) -> dict:
    """Project instance data onto the ontology as nodes and typed edges.

    With `focus` (an opportunity ID) returns that opportunity's neighbourhood; otherwise the
    portfolio graph of active opportunities and their shared counterparties, countries,
    regions, domains and sponsors.
    """
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(nid: str, cls: str, label: str, **meta) -> str:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "class": cls, "label": label, **meta}
        return nid

    def edge(a: str, rel: str, b: str) -> None:
        edges.append({"source": a, "target": b, "relation": rel})

    opps = [snap.opp(focus)] if focus else snap.active
    for o in filter(None, opps):
        s = snap.scores.get(o["id"], {})
        oid = node(o["id"], "Opportunity", o["name"], value=o.get("value"), p=s.get("p"), ev=s.get("ev"),
                   stage=o.get("status"), risk=s.get("risk"))
        if o.get("counterparty"):
            edge(oid, "hasCounterparty", node("cp:" + o["counterparty"], "Counterparty", o["counterparty"].replace("Example: ", "")))
        if o.get("country"):
            cid = node("country:" + o["country"], "Country", o["country"])
            edge(oid, "locatedIn", cid)
            reg = region_of(o["country"])
            if reg:
                edge(cid, "partOfRegion", node("region:" + reg, "Region", reg))
        if o.get("site"):
            sid = node("site:" + o["id"], "Site", o["site"], lat=o.get("lat"), lon=o.get("lon"))
            edge(oid, "deployedAt", sid)
        if o.get("domain"):
            edge(oid, "inDomain", node("domain:" + o["domain"], "Domain", o["domain"]))
        if o.get("status"):
            edge(oid, "atStage", node("stage:" + o["status"], "Stage", o["status"]))
        if o.get("sponsor"):
            edge(oid, "sponsoredBy", node("person:" + o["sponsor"], "ExecutiveSponsor", o["sponsor"]))
        if focus:
            if o.get("owner"):
                edge(oid, "ownedBy", node("person:" + o["owner"], "ExecutionalOwner", o["owner"]))
            if o.get("outlook"):
                edge(oid, "hasOutlook", node("outlook:" + o["outlook"], "Outlook", o["outlook"]))
            pid = node("pred:" + o["id"], "Prediction", f"p={round(s.get('p', 0) * 100)}%", p=s.get("p"), ev=s.get("ev"))
            edge(oid, "hasPrediction", pid)
            for f in s.get("factors", [])[1:]:
                edge(pid, "explainedBy", node(f"factor:{o['id']}:{f['key']}", "ScoreFactor", f["label"], impact=f["impact"]))
        if include_events and focus:
            for e in [e for e in snap.engs if e["opp"] == o["id"]][-6:]:
                edge(oid, "hasEngagement", node(e["id"], "Engagement", f"{e.get('date')} {e.get('type')}", summary=e.get("summary")))
            for a in [a for a in snap.acts if a["opp"] == o["id"]]:
                aid = node(a["id"], "Action", a.get("title") or a["id"], status=a.get("status"))
                edge(oid, "hasAction", aid)
                if a.get("owner"):
                    edge(aid, "accountable", node("person:" + a["owner"], "Person", a["owner"]))
            for a in [a for a in snap.anns if a["opp"] == o["id"]]:
                nid = node(a["id"], "Announcement", a.get("title") or a["id"], readiness=a.get("readiness"))
                edge(oid, "hasAnnouncement", nid)
                for k, lab in (("legal", "Legal"), ("ir", "IR"), ("counterparty", "Counterparty")):
                    edge(nid, "requiresApproval", node(f"appr:{a['id']}:{k}", "Approval", f"{lab}: {a.get(k) or '—'}", state=a.get(k)))
    return {"nodes": list(nodes.values()), "edges": edges, "focus": focus}
