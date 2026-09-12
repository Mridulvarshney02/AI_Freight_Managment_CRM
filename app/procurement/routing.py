import re
import sqlite3


def key(value):
    return " ".join(
        (value or "").replace("\xa0", " ").casefold().split()
    )


def office_rule(method, region):
    text = key(method)

    if "online spot rate only" in text:
        return "portal", [], [], None

    single = re.search(
        r"single ([a-z/]+) office(?: \(([a-z/]+)\))?",
        text,
    )

    if single and "handles all por" in text:
        offices = single.group(1).split("/")

        if single.group(2):
            offices += single.group(2).split("/")

        return "office", sorted(set(offices)), [], None

    if region == "delhi" and (
        "delhi office for delhi" in text
        or "delhi office covers jaipur and all ncr regions" in text
    ):
        fallback = (
            ["jaipur"]
            if "jaipur office can quote for delhi" in text
            else []
        )
        return "office", ["delhi"], fallback, None

    if region == "jaipur":
        if "jaipur office for jaipur" in text:
            fallback = (
                ["delhi"]
                if "delhi office can quote for jaipur" in text
                else []
            )
            return "office", ["jaipur"], fallback, None

        if "delhi office covers jaipur" in text:
            return "office", ["delhi"], [], None

    if region == "mundra" and any(
        fragment in text
        for fragment in (
            "mundra again separate",
            "mundra office for mundra",
            "mundra por rates to get from mundra office",
        )
    ):
        return "office", ["mundra"], [], None

    return (
        None,
        [],
        [],
        "Office rule is missing or uses an unsupported instruction format.",
    )


def office_labels(value):
    # Handle labels such as Jaipur/Jodhpur and Mumbai (HO).
    base = re.sub(r"\([^)]*\)", "", key(value))

    return {
        key(part)
        for part in base.split("/")
        if key(part)
    }


def add_routing(plan, booking_region, container_type, db_path):
    region = key(booking_region)
    equipment = key(container_type).replace(" ", "").upper()

    if not re.fullmatch(
        r"(20|40|45)(DV|GP|DC|HC|HQ|RF|OT|FR)?",
        equipment,
    ):
        raise ValueError(
            "Use an equipment type such as 20DV or 40HC."
        )

    with sqlite3.connect(
        db_path.as_uri() + "?mode=ro",
        uri=True,
    ) as db:
        db.row_factory = sqlite3.Row

        contacts = [
            dict(row)
            for row in db.execute("""
                SELECT * FROM shipping_line_contacts
                ORDER BY source_row
            """)
        ]

        names = {
            row["id"]: row["shipping_line_name"]
            for row in db.execute("""
                SELECT id, shipping_line_name
                FROM procurement_entries
            """)
        }

    plan["booking_region"] = booking_region
    plan["container_type"] = equipment

    for candidate in plan["candidates"]:
        channel, offices, fallbacks, issue = office_rule(
            candidate["rate_getting_system"],
            region,
        )

        name = names[candidate["entry_id"]]
        carrier_key = key(name)

        related = [
            contact
            for contact in contacts
            if contact["procurement_match_key"] == carrier_key
        ]

        def matching(locations):
            fields = (
                "id",
                "shipping_line_name",
                "booking_agency",
                "office_location",
                "contact_person",
                "email_address",
                "contact_number",
                "source_row",
            )

            return [
                {field: contact[field] for field in fields}
                for contact in related
                if office_labels(contact["office_location"])
                & set(locations)
            ]

        routing = {
            "channel": channel,
            "required_offices": offices,
            "documented_fallback_offices": fallbacks,
            "contact_candidates": matching(offices),
            "fallback_contact_candidates": matching(fallbacks),
            "issues": [issue] if issue else [],
        }

        candidate["routing"] = routing
        remarks = key(candidate.get("remarks"))

        # Specific conflict present in the current workbook.
        agency_conflict = (
            "parekh marine" in carrier_key
            and re.search(
                r"represented by poseidon shipping agency",
                remarks,
            )
        )

        if agency_conflict:
            routing["status"] = "agency_conflict"
            routing["issues"].append(
                "Carrier label names Parekh Marine; "
                "remarks name Poseidon/Abrao. Resolve representation."
            )
            routing["contact_candidates"] = []
            routing["fallback_contact_candidates"] = []

        elif candidate["coverage_status"] == "carrier_identity_review":
            routing["status"] = "carrier_identity_review"

        elif channel == "portal":
            routing["status"] = "portal_identified"

        elif not offices:
            routing["status"] = "office_rule_missing"

        elif routing["contact_candidates"]:
            routing["status"] = "contacts_found_for_review"

        elif routing["fallback_contact_candidates"]:
            routing["status"] = "documented_fallback_available"

        else:
            routing["status"] = "required_office_contact_missing"

        restricted = bool(re.search(
            r"\b20\s*(?:ft|foot)\s+containers?\s+only\b",
            remarks,
        ))

        if restricted and not equipment.startswith("20"):
            candidate["equipment_status"] = (
                "conflicts_with_20ft_only_note"
            )
        elif restricted:
            candidate["equipment_status"] = (
                "consistent_with_20ft_size_note"
            )
        else:
            candidate["equipment_status"] = (
                "acceptance_not_confirmed"
            )

        if routing["status"] in (
            "agency_conflict",
            "carrier_identity_review",
        ):
            action = "Resolve carrier/agency identity before outreach."

        elif candidate["equipment_status"] == "conflicts_with_20ft_only_note":
            action = (
                "Review the workbook's 20ft-only restriction "
                "before requesting this equipment."
            )

        elif channel == "portal":
            action = (
                "Use the designated quotation tool to check the exact "
                "route and equipment; portal access is not implemented."
            )

        elif routing["status"] == "contacts_found_for_review":
            action = (
                "Review recipient suitability, then prepare a route/rate "
                "enquiry; no message has been sent."
            )

        elif routing["status"] == "documented_fallback_available":
            action = (
                "A contact is available at an office explicitly permitted "
                "by the workbook's fallback rule. Review recipient "
                "suitability before preparing the enquiry."
            )

            if candidate["coverage_status"] == "coverage_check_required":
                action += (
                    " Ask the carrier to confirm service to the requested "
                    "POD along with the quotation."
                )

        elif offices:
            action = (
                "Obtain a contact for the required office. "
                "No usable documented fallback contact was found."
            )

        else:
            action = "Resolve the carrier's office instructions."

        candidate["next_action"] = action

    return plan