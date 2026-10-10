import argparse
import json
import re
from sqlalchemy import text
from app.procurement.pg_database import get_engine
from pathlib import Path
from app.procurement.routing import add_routing

DB_PATH = Path(__file__).resolve().parent / "procurement.db"


def key(value):
    return " ".join(
        (value or "").replace("\xa0", " ").casefold().split()
    )


def setup():
    raise RuntimeError("Reference configuration is migrated from SQLite. Do not rerun legacy setup.")


def lookup(pol, pod, *, resolve_missing=False):
    with get_engine().connect() as db:
        aliases = dict(db.execute(text(
            "SELECT alias_key, port_key FROM procurement.port_aliases"
        )).tuples().all())
        scopes = set(db.execute(text(
            "SELECT lane_key, pol_key FROM procurement.lane_origin_scope"
        )).tuples().all())
        rows = [dict(row) for row in db.execute(text(
            "SELECT * FROM procurement.procurement_entries ORDER BY source_row, id"
        )).mappings()]

    def canonical(value):
        result = key(value)
        seen = set()

        while result in aliases:
            if result in seen:
                raise ValueError("Circular port alias configuration")

            seen.add(result)
            target = key(aliases[result])

            if target == result:
                break

            result = target

        return result

    def ports(value):
        text = (value or "").strip()

        if not text:
            return set()

        # Keep qualified or negative coverage statements under review.
        review_markers = (
            "no service",
            "no rates",
            "no spot",
            "pending",
            "not verified",
            "via ",
            "@",
        )

        if any(marker in text.casefold() for marker in review_markers):
            return set()

        # Recognize the section headings present in the HMM workbook cell.
        # Only remove headings at the beginning of a section.
        text = re.sub(
            r"(^|[;\r\n])\s*(?:MED|EUROPE)\s*:\s*",
            r"\1",
            text,
            flags=re.IGNORECASE,
        )

        result = set()

        for part in re.split(r"[,;\r\n]", text):
            token = part.strip()

            if not token:
                continue

            # Leave individual qualified entries for later interpretation.
            # They must not prevent other plain ports from being matched.
            if any(character in token for character in "():"):
                continue

            result.add(canonical(token))

        return result

    origin = canonical(pol)
    destination = canonical(pod)

    destination_rows = [
        row for row in rows
        if destination in ports(row["ports_covered"])
    ]

    matching_lanes = {
        key(row["trade_lane"])
        for row in destination_rows
        if (key(row["trade_lane"]), origin) in scopes
    }
    port_resolution = None

    if not matching_lanes and resolve_missing:
        from app.procurement.port_resolver import resolve_port_lane

        eligible_lanes = sorted({
            row["trade_lane"].strip()
            for row in rows
            if row["trade_lane"]
            and (key(row["trade_lane"]), origin) in scopes
        })

        port_resolution = resolve_port_lane(
            pol=pol,
            pod=pod,
            eligible_lanes=eligible_lanes,
        )

        if port_resolution["status"] == "matched":
            matching_lanes = {
                key(lane)
                for lane in port_resolution["trade_lanes"]
            }

    configured_lanes = {scope[0] for scope in scopes}

    unconfigured = sorted({
        row["trade_lane"]
        for row in destination_rows
        if key(row["trade_lane"]) not in configured_lanes
    })

    result = {
        "pol": pol,
        "pod": pod,
        "lane_resolution_method": None,
        "resolved_pod": destination,
        "status": (
            "workbook_candidates_found"
            if matching_lanes else "discovery_required"
        ),
        "trade_lanes": sorted({
            row["trade_lane"].strip()
            for row in rows
            if key(row["trade_lane"]) in matching_lanes
        }),
        "lanes_missing_origin_configuration": unconfigured,
        "candidates": [],
    }

    for row in rows:
        if key(row["trade_lane"]) not in matching_lanes:
            continue

        name = row["shipping_line_name"] or ""
        malformed = (
            len(name) > 150
            or any(character in name for character in "\t\n@")
        )

        listed = destination in ports(row["ports_covered"])

        if malformed:
            status = "carrier_identity_review"
        elif listed:
            status = "destination_listed"
        else:
            status = "coverage_check_required"

        result["candidates"].append({
            "entry_id": row["id"],
            "source_row": row["source_row"],
            "shipping_line": (
                "[Carrier name needs correction]"
                if malformed else name.strip()
            ),
            "coverage_status": status,
            "rate_getting_system": row["rate_getting_system"],
            "ports_covered": row["ports_covered"],
            "remarks": row["remarks"],
        })
    result["lane_resolution_method"] = "workbook" if matching_lanes else None
    if port_resolution is not None:
        result["port_resolution"] = port_resolution
        if port_resolution["status"] == "matched":
            result["lane_resolution_method"] = "search_assisted"
        else:
            result["status"] = port_resolution["status"]
            result["next_action"] = (
                port_resolution.get("clarification_question")
                or port_resolution["explanation"]
            )
    elif not matching_lanes:
        result["next_action"] = "Port or origin scope needs review; this does not mean no service."

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--pol")
    parser.add_argument("--pod")
    parser.add_argument("--booking-region")
    parser.add_argument("--container-type")
    args = parser.parse_args()

    if args.setup:
        setup()

    else:
        if not key(args.pol) or not key(args.pod):
            parser.error("Provide --pol and --pod")

        include_routing = (
            args.booking_region is not None
            or args.container_type is not None
        )

        if include_routing and (
            not key(args.booking_region)
            or not key(args.container_type)
        ):
            parser.error(
                "Provide both --booking-region and --container-type"
            )

        plan = lookup(args.pol, args.pod, resolve_missing=True)

        if include_routing:
            try:
                plan = add_routing(
                    plan,
                    args.booking_region,
                    args.container_type,
                    DB_PATH,
                )
            except ValueError as exc:
                parser.error(str(exc))

        print(json.dumps(
            plan,
            indent=2,
            ensure_ascii=False,
        ))