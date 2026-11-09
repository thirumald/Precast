"""Illustrative seed data. Every counterparty is prefixed "Example:" — none of it is real."""
from __future__ import annotations

from datetime import date, timedelta

from . import db


def _d(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


# (id, name, country, city/site, lat, lon, domain, segment, counterparty, type, sponsor, owner,
#  priority, commercial, value, status, outlook, milestone, milestone_in, intervention, announce,
#  verified_ago, latest, rationale, next_action, competitors)
ACTIVE = [
    ("OPP-001", "National command-and-control platform", "UAE", "Abu Dhabi national C2 centre", 24.4539, 54.3773,
     "Security", "Government", "Example: Federal Security Authority", "Commercial Contract", "Chief Executive Officer",
     "Head of Public Safety", 5, 5, 420e6, "Negotiation", "Positive", "Final commercial terms session", 9, "Yes", "Yes", 4,
     "Technical evaluation completed; shortlisted with one other bidder.", "Strong technical score and sponsor alignment.",
     "Align pricing envelope with Finance before final session.", 1),
    ("OPP-002", "Smart city analytics rollout, phase 2", "Saudi Arabia", "Riyadh municipal districts", 24.7136, 46.6753,
     "Urban", "Government", "Example: Municipal Development Authority", "Strategic Partnership", "Chief Operating Officer",
     "Director, Urban Solutions", 4, 4, 185e6, "Proposal", "Positive", "Proposal submission", 14, "No", "Under Consideration", 8,
     "Phase 1 pilot KPIs met in three districts.", "Pilot results give a credible base for scale-up.",
     "Submit phased proposal with local partner annex.", 2),
    ("OPP-003", "Sovereign fund risk intelligence suite", "UAE", "Abu Dhabi financial district", 24.5004, 54.3906,
     "Financial", "Enterprise", "Example: Sovereign Investment Group", "Commercial Contract", "Chief Commercial Officer",
     "Head of Financial Services", 4, 3, 62e6, "Active Engagement", "Neutral", "Executive workshop", 21, "No", "No", 35,
     "Client reprioritising budget cycle for next year.", "Budget timing uncertain.",
     "Confirm budget owner and decision calendar.", 1),
    ("OPP-004", "Border surveillance data fusion", "Kazakhstan", "Southern border sector", 43.2389, 76.8897,
     "Defense", "Government", "Example: Ministry of Interior", "Joint Venture", "Chief Executive Officer",
     "Director, Defense Programs", 5, 4, 240e6, "Negotiation", "Negative", "JV term sheet sign-off", -6, "Yes", "Yes", 12,
     "Counterparty requested revised local-content share.", "Local-content demand exceeds current JV structure.",
     "CEO-to-minister call to reset JV parameters.", 3),
    ("OPP-005", "Grid resilience and demand forecasting", "Egypt", "Cairo grid control centre", 30.0444, 31.2357,
     "Energy", "Government", "Example: National Electricity Holding", "MoU", "Chief Strategy Officer",
     "Head of Energy", 3, 3, 48e6, "Exploratory", "Neutral", "Discovery workshop", 30, "No", "No", 20,
     "Initial requirements shared.", "Early stage; requirements still forming.",
     "Run discovery workshop with grid operations team.", 2),
    ("OPP-006", "Emergency response digital twin", "UAE", "Dubai civil defence operations", 25.2048, 55.2708,
     "Urban", "Government", "Example: Civil Defence Directorate", "Commercial Contract", "Chief Operating Officer",
     "Director, Urban Solutions", 4, 3, 78e6, "Agreement", "Positive", "Contract signature", 5, "No", "Yes", 2,
     "Legal review of contract complete.", "Commercial terms agreed.", "Arrange signature ceremony logistics.", 0),
    ("OPP-007", "Anti-financial-crime analytics", "Indonesia", "Jakarta HQ", -6.2088, 106.8456,
     "Financial", "Enterprise", "Example: Regional Banking Group", "Market Access", "Chief Commercial Officer",
     "Head of Financial Services", 3, 4, 130e6, "Proposal", "Neutral", "Proof-of-value results", 18, "No", "No", 41,
     "Competing global vendor entered process.", "Competitive pressure on pricing.",
     "Prepare differentiated proof-of-value scope.", 4),
    ("OPP-008", "Critical infrastructure cyber-fusion centre", "Saudi Arabia", "Jeddah fusion centre", 21.4858, 39.1925,
     "Security", "Government", "Example: National Cyber Agency", "Strategic Partnership", "Chief Executive Officer",
     "Head of Public Safety", 5, 4, 160e6, "Active Engagement", "Positive", "Joint steering committee", 12, "Yes",
     "Under Consideration", 6, "Steering committee formed; sponsor confirmed at deputy-minister level.",
     "High-level sponsorship secured.", "Confirm CEO attendance at steering committee.", 2),
    ("OPP-009", "Upstream asset monitoring AI", "Kenya", "Turkana field sites", 3.1191, 35.5973,
     "Energy", "Enterprise", "Example: Energy Exploration Company", "Commercial Contract", "Chief Strategy Officer",
     "Head of Energy", 2, 2, 14e6, "Execution", "Positive", "Go-live, site 2", 26, "No", "No", 9,
     "Site 1 live and stable.", "Delivery on plan.", "Mobilise site 2 deployment team.", 0),
    ("OPP-010", "Defense logistics optimisation", "UAE", "Al Ain logistics command", 24.2075, 55.7447,
     "Defense", "Government", "Example: Armed Forces Logistics Command", "Commercial Contract", "Chief Operating Officer",
     "Director, Defense Programs", 4, 3, 55e6, "Proposal", "Negative", "Clarification responses", -2, "Yes", "No", 50,
     "Security clearance for delivery staff delayed.", "Clearance delays put timeline at risk.",
     "Escalate clearance processing with sponsor.", 1),
    ("OPP-011", "Population health analytics partnership", "Morocco", "Rabat planning agency", 34.0209, -6.8416,
     "Urban", "Government", "Example: Health Planning Agency", "MoU", "Chief Strategy Officer",
     "Director, Urban Solutions", 3, 2, 22e6, "Exploratory", "Neutral", "MoU draft exchange", 38, "No",
     "Under Consideration", 15, "Draft MoU shared by counterparty.", "Interest confirmed; scope undefined.",
     "Return MoU mark-up.", 1),
    ("OPP-015", "Safe city video analytics, Tirana", "Albania", "Tirana city centre", 41.3275, 19.8187,
     "Security", "Government", "Example: State Police Directorate", "Commercial Contract", "Chief Commercial Officer",
     "Head of Public Safety", 4, 4, 115e6, "Negotiation", "Positive", "BRD sign-off", 11, "No", "Under Consideration", 5,
     "Business requirements annex agreed in principle.", "Scope converging; counterparty engaged weekly.",
     "Close open BRD comments and lock UAT criteria.", 2),
    ("OPP-016", "Intelligent transport crosswalk programme", "Azerbaijan", "Baku arterial corridors", 40.4093, 49.8671,
     "Urban", "Government", "Example: Transport Agency", "Commercial Contract", "Chief Operating Officer",
     "Director, Urban Solutions", 3, 3, 36e6, "Proposal", "Positive", "POC results review", 16, "No", "No", 10,
     "Phase 1 POC sites installed.", "POC performing; budget allocated.", "Present POC results to agency board.", 3),
    ("OPP-017", "Smart campus safety platform", "Saudi Arabia", "Qassim campus", 26.3489, 43.7668,
     "Security", "Government", "Example: Public University", "Commercial Contract", "Chief Commercial Officer",
     "Head of Public Safety", 3, 2, 18e6, "Active Engagement", "Neutral", "POC scoping", 20, "No", "No", 28,
     "Existing camera estate audited.", "Integration with incumbent VMS unclear.", "Agree POC scope and success criteria.", 2),
    ("OPP-018", "National traffic enforcement platform", "Dominican Republic", "Santo Domingo corridors", 18.4861, -69.9312,
     "Urban", "Government", "Example: National Traffic Directorate", "Commercial Contract", "Chief Operating Officer",
     "Director, Urban Solutions", 4, 4, 140e6, "Execution", "Positive", "Phase 2 handover", 33, "No", "Yes", 7,
     "Phase 1 enforcement corridors live.", "Delivery ahead of plan.", "Prepare phase 2 acceptance pack.", 0),
    ("OPP-019", "Smart city command centre, Podgorica", "Montenegro", "Podgorica city", 42.4304, 19.2594,
     "Urban", "Government", "Example: Capital City Authority", "Commercial Contract", "Chief Commercial Officer",
     "Director, Urban Solutions", 3, 3, 44e6, "Proposal", "Negative", "Commercial review", -9, "No", "No", 47,
     "Client questioned camera inventory pricing.", "Price sensitivity and slow responses.", "Re-baseline BoQ and request meeting.", 3),
    ("OPP-020", "Renewable fleet performance AI", "Uzbekistan", "Tashkent energy ministry", 41.2995, 69.2401,
     "Energy", "Government", "Example: Energy Ministry", "Strategic Engagement", "Chief Strategy Officer",
     "Head of Energy", 3, 3, 52e6, "Active Engagement", "Positive", "Follow-up workshop", 8, "No", "No", 9,
     "Ministry requested a joint workshop after first meeting.", "Strong initial interest.", "Prepare workshop agenda.", 1),
]

INACTIVE = [
    ("OPP-012", "Trade finance fraud detection", "UAE", "Dubai", 25.2582, 55.3047, "Financial", "Enterprise",
     "Example: Trade Finance Bank", "Closed Won", "Positive", 31e6, -20),
    ("OPP-013", "Port security video analytics", "Oman", "Muscat port", 23.6260, 58.5655, "Security", "Government",
     "Example: Ports Authority", "Closed Lost", "Negative", 9e6, -60),
    ("OPP-014", "Renewables yield forecasting", "Uzbekistan", "Samarkand", 39.6270, 66.9750, "Energy", "Government",
     "Example: Renewable Energy Agency", "On Hold", "Neutral", 40e6, None),
]

# Historical closed deals give the scoring model real win/loss ratios to calibrate against.
HISTORY = [
    ("Security", "Closed Won", 85e6), ("Security", "Closed Won", 40e6), ("Security", "Closed Lost", 22e6),
    ("Security", "Closed Won", 12e6), ("Security", "Closed Lost", 60e6), ("Security", "Closed Won", 30e6),
    ("Defense", "Closed Lost", 120e6), ("Defense", "Closed Won", 75e6), ("Defense", "Closed Lost", 40e6),
    ("Defense", "Closed Lost", 18e6),
    ("Urban", "Closed Won", 55e6), ("Urban", "Closed Won", 26e6), ("Urban", "Closed Won", 14e6),
    ("Urban", "Closed Lost", 33e6), ("Urban", "Closed Won", 70e6),
    ("Financial", "Closed Lost", 15e6), ("Financial", "Closed Won", 24e6), ("Financial", "Closed Lost", 48e6),
    ("Energy", "Closed Won", 19e6), ("Energy", "Closed Lost", 27e6), ("Energy", "Closed Won", 35e6),
]
HIST_PLACES = [("UAE", 24.45, 54.38), ("Saudi Arabia", 24.71, 46.68), ("Egypt", 30.04, 31.24), ("Kazakhstan", 51.17, 71.45),
               ("Jordan", 31.95, 35.93), ("Serbia", 44.79, 20.45), ("Georgia", 41.72, 44.79), ("Bahrain", 26.23, 50.59)]

# (opp, days_ago, type, summary, follow_up, due_in)
ENGAGEMENTS = [
    ("OPP-001", 52, "Meeting", "Technical deep-dive went well; evaluators impressed with integration demo.", "Send architecture pack", -45),
    ("OPP-001", 31, "Workshop", "Joint workshop agreed phased rollout and acceptance criteria.", "Draft acceptance plan", -20),
    ("OPP-001", 16, "Meeting", "Commercial clarification session; client positive on value but asked for pricing flexibility.", "Revise pricing options", -9),
    ("OPP-001", 4, "Executive Engagement", "Sponsor confirmed preference to close this quarter.", "Finance sign-off on pricing", 4),
    ("OPP-002", 70, "Event", "Phase 1 pilot launched in three districts.", "Monitor pilot KPIs", -40),
    ("OPP-002", 35, "Meeting", "Pilot KPIs exceeded targets; municipality keen to scale.", "Scope phase 2", -15),
    ("OPP-002", 8, "Event", "Pilot results presented to municipal leadership; strong support.", "Draft phase 2 proposal", 10),
    ("OPP-003", 80, "Meeting", "Introductory session with risk office; interest confirmed.", "Share capability deck", -70),
    ("OPP-003", 35, "Call", "Client reprioritising budget; decision delayed to next cycle.", "Confirm budget owner", -9),
    ("OPP-004", 60, "Meeting", "Ministry agreed JV concept and governance outline.", "Draft term sheet", -40),
    ("OPP-004", 30, "Call", "Concerns raised over data sovereignty clauses.", "Legal response", -20),
    ("OPP-004", 12, "Call", "Counterparty raised local-content requirement to 60%; tense discussion, risk of stalling.", "Revise JV model", -6),
    ("OPP-005", 20, "Email", "Initial requirements shared by grid operations team.", "Schedule discovery workshop", 30),
    ("OPP-006", 45, "Meeting", "Commercial terms agreed in principle.", "Legal review", -30),
    ("OPP-006", 18, "Meeting", "Legal comments resolved quickly; client supportive.", "Final contract", -5),
    ("OPP-006", 2, "Meeting", "Legal teams closed final contract comments.", "Plan signature ceremony", 3),
    ("OPP-007", 65, "Meeting", "Positive discovery session with compliance team.", "Proof-of-value proposal", -50),
    ("OPP-007", 41, "Email", "Client confirmed a second vendor is in evaluation; pricing pressure expected.", "Scope proof-of-value", 12),
    ("OPP-008", 40, "Meeting", "Agency confirmed strategic intent for national fusion centre.", "Prepare governance proposal", -25),
    ("OPP-008", 21, "Workshop", "Use-case prioritisation workshop; strong alignment.", "Steering committee ToR", -10),
    ("OPP-008", 6, "Meeting", "Steering committee terms of reference agreed.", "Prepare steering pack", 9),
    ("OPP-009", 30, "Meeting", "Site 1 go-live accepted by client.", "Plan site 2", -10),
    ("OPP-009", 9, "Call", "Client happy with site 1 stability.", "Mobilise site 2", 20),
    ("OPP-010", 75, "Meeting", "Requirements clarified; client keen.", "Submit proposal", -60),
    ("OPP-010", 50, "Call", "Clearance processing delayed by documentation gaps; concern over timeline.", "Escalation letter", -3),
    ("OPP-011", 15, "Email", "Draft MoU shared by counterparty.", "Return MoU mark-up", 38),
    ("OPP-015", 48, "Workshop", "BRD walkthrough with State Police; constructive.", "Respond to BRD comments", -30),
    ("OPP-015", 26, "Meeting", "UAT approach agreed; client supportive of phased go-live.", "Draft UAT plan", -12),
    ("OPP-015", 12, "Meeting", "Scope change requests reviewed; most accepted.", "Update compliance matrix", -2),
    ("OPP-015", 5, "Call", "Business requirements annex agreed in principle.", "Lock UAT criteria", 11),
    ("OPP-016", 40, "Event", "POC sites installed at two crosswalks.", "Collect POC data", -10),
    ("OPP-016", 10, "Meeting", "POC data shows strong safety improvement; agency impressed.", "Board presentation", 16),
    ("OPP-017", 28, "Meeting", "Camera estate audit completed; integration questions with incumbent.", "POC scope", 20),
    ("OPP-018", 55, "Meeting", "Phase 1 corridors accepted.", "Phase 2 mobilisation", -30),
    ("OPP-018", 7, "Meeting", "Directorate praised enforcement results; phase 2 on track.", "Acceptance pack", 33),
    ("OPP-019", 47, "Email", "Client questioned camera inventory pricing; responses slow.", "Re-baseline BoQ", -9),
    ("OPP-020", 9, "Meeting", "First meeting with ministry; strong interest, requested joint workshop.", "Workshop agenda", 8),
]

# (opp, title, category, owner, due_in, status, priority, blocker, escalate, created_ago)
ACTIONS = [
    ("OPP-001", "Finance sign-off on pricing envelope", "Commercial", "CFO Office", 4, "In Progress", "Critical", "", "No", 10),
    ("OPP-004", "Revised JV local-content model", "Legal", "Director, Defense Programs", -6, "Blocked", "Critical", "Awaiting counterparty data", "Yes", 12),
    ("OPP-010", "Clearance escalation letter", "Executive", "Chief Operating Officer", -3, "Not Started", "High", "Sponsor availability", "Yes", 20),
    ("OPP-002", "Local partner annex", "Commercial", "Director, Urban Solutions", 10, "In Progress", "High", "", "No", 7),
    ("OPP-006", "Signature ceremony plan", "Communications", "Communications Lead", 3, "In Progress", "Normal", "", "No", 2),
    ("OPP-007", "Proof-of-value scope", "Technical", "Head of Financial Services", 12, "Not Started", "High", "", "No", 30),
    ("OPP-008", "Steering committee pack", "Executive", "Head of Public Safety", 9, "In Progress", "Critical", "", "No", 6),
    ("OPP-003", "Confirm budget owner", "Commercial", "Head of Financial Services", -9, "In Progress", "Normal", "", "No", 30),
    ("OPP-009", "Site 2 mobilisation", "Technical", "Head of Energy", 20, "Not Started", "Normal", "", "No", 9),
    ("OPP-015", "Lock UAT acceptance criteria", "Technical", "Head of Public Safety", 11, "In Progress", "High", "", "No", 5),
    ("OPP-019", "Re-baselined BoQ submission", "Commercial", "Director, Urban Solutions", -9, "Blocked", "High", "Awaiting OEM pricing", "Yes", 40),
    ("OPP-016", "POC results board deck", "Executive", "Director, Urban Solutions", 14, "In Progress", "Normal", "", "No", 10),
    ("OPP-017", "Integration API access from incumbent VMS vendor", "Technical", "Head of Public Safety", -4, "Blocked", "High", "Incumbent vendor withholding SDK licence", "Yes", 18),
]

# (id, opp, title, type, target_in, readiness, legal, ir, cp, event)
ANNOUNCEMENTS = [
    ("ANN-001", "OPP-001", "National C2 platform contract award", "Contract Award", 28, "Pending Approvals", "Pending", "Pending", "Pending", "Press release + IDEX"),
    ("ANN-002", "OPP-006", "Emergency response digital twin signing", "Contract Award", 8, "Approved", "Approved", "Approved", "Approved", "Signing ceremony"),
    ("ANN-003", "OPP-004", "Border data-fusion JV launch", "JV Launch", 45, "Deferred", "Pending", "Not Required", "Rejected", "Joint press conference"),
    ("ANN-004", "OPP-012", "Trade finance fraud detection win", "Partnership", 14, "Planning", "Approved", "Pending", "Pending", "LinkedIn + press"),
    ("ANN-005", "OPP-018", "National traffic enforcement phase 2", "Milestone", 35, "Planning", "Pending", "Pending", "Approved", "Ministry event"),
]


def seed(force: bool = False) -> bool:
    if db.count("opportunities") and not force:
        return False
    if force:
        db.clear_all()
    for r in ACTIVE:
        (oid, name, country, site, lat, lon, domain, seg, cp, typ, sponsor, owner, p, c, v, status, outlook,
         ms, ms_in, inter, ann, ver, latest, rat, nxt, comp) = r
        db.upsert("opportunities", dict(
            id=oid, name=name, country=country, site=site, lat=lat, lon=lon, domain=domain, segment=seg,
            counterparty=cp, type=typ, sponsor=sponsor, owner=owner, priority=p, commercial=c, value=v,
            status=status, outlook=outlook, milestone=ms, milestone_date=_d(ms_in), intervention=inter,
            announce=ann, verified=_d(-ver), latest=latest, rationale=rat, next_action=nxt, action_owner=owner,
            sensitivity="Confidential", source="Example record", competitors=comp, created=_d(-120)))
    for oid, name, country, site, lat, lon, domain, seg, cp, status, outlook, v, closed in INACTIVE:
        db.upsert("opportunities", dict(
            id=oid, name=name, country=country, site=site, lat=lat, lon=lon, domain=domain, segment=seg,
            counterparty=cp, type="Commercial Contract", sponsor="Chief Commercial Officer",
            owner="Head of Financial Services" if domain == "Financial" else "Head of Public Safety",
            priority=3 if status != "Closed Lost" else 2, commercial=3 if v > 25e6 else 2, value=v, status=status,
            outlook=outlook, milestone="Kick-off" if status == "Closed Won" else "", milestone_date=_d(7) if status == "Closed Won" else None,
            intervention="No", announce="Yes" if status == "Closed Won" else "No", verified=_d(-5),
            latest={"Closed Won": "Contract signed.", "Closed Lost": "Awarded to incumbent.", "On Hold": "Counterparty restructuring."}[status],
            rationale="", sensitivity="Confidential", source="Example record", created=_d(-200),
            closed=_d(closed) if closed is not None else None))
    for i, (dom, status, v) in enumerate(HISTORY, start=1):
        country, lat, lon = HIST_PLACES[i % len(HIST_PLACES)]
        db.upsert("opportunities", dict(
            id=f"HIS-{i:03d}", name=f"Historical {dom.lower()} engagement {i}", country=country, lat=lat, lon=lon,
            domain=dom, segment="Government", counterparty="Example: historical client", type="Commercial Contract",
            sponsor="Chief Commercial Officer", owner="Sales", priority=3, commercial=3, value=v, status=status,
            outlook="Positive" if status == "Closed Won" else "Negative", verified=_d(-200), created=_d(-600),
            closed=_d(-400 + i * 12), source="Historical record"))
    for i, (opp, ago, typ, summary, follow, due_in) in enumerate(ENGAGEMENTS, start=1):
        db.upsert("engagements", dict(
            id=f"ENG-{i:03d}", opp=opp, date=_d(-ago), type=typ, summary=summary, follow_up=follow,
            due=_d(due_in), external="Counterparty team", internal="Presight team", source="seed"))
    for i, (opp, title, cat, owner, due_in, status, pr, blocker, esc, created) in enumerate(ACTIONS, start=1):
        db.upsert("actions", dict(
            id=f"ACT-{i:03d}", opp=opp, title=title, category=cat, owner=owner, due=_d(due_in), status=status,
            priority=pr, blocker=blocker, escalate=esc, created=_d(-created)))
    for aid, opp, title, typ, t_in, ready, legal, ir, cp, event in ANNOUNCEMENTS:
        db.upsert("announcements", dict(
            id=aid, opp=opp, title=title, type=typ, target=_d(t_in), readiness=ready, legal=legal, ir=ir,
            counterparty=cp, event=event, lead="Communications Lead", disclose="No"))
    # Keep last_engagement in step with the log.
    for o in db.all_rows("opportunities"):
        engs = db.all_rows("engagements", "opp=?", (o["id"],))
        if engs:
            db.update("opportunities", o["id"], {"last_engagement": max(e["date"] for e in engs)})
    return True
