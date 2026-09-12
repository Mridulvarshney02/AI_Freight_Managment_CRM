import argparse
import json
import re
import sqlite3
from pathlib import Path
from app.procurement.routing import add_routing

DB_PATH = Path(__file__).resolve().parent / "procurement.db"


def key(value):
    return " ".join(
        (value or "").replace("\xa0", " ").casefold().split()
    )


def setup():
    with sqlite3.connect(
        DB_PATH.as_uri() + "?mode=rw", uri=True
    ) as db:
        db.execute("BEGIN")

        db.execute("""
            CREATE TABLE IF NOT EXISTS port_aliases (
                alias_key TEXT PRIMARY KEY,
                port_key TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS lane_origin_scope (
                lane_key TEXT NOT NULL,
                pol_key TEXT NOT NULL,
                PRIMARY KEY (lane_key, pol_key)
            )
        """)

        db.execute(
            "INSERT OR IGNORE INTO port_aliases VALUES (?, ?)",
            ("sokhna", "al sokhna"),
        )

        lanes = db.execute(
            "SELECT DISTINCT trade_lane FROM procurement_entries"
        ).fetchall()

        for (lane,) in lanes:
            label = key(lane)
            origins = []

            # Initial origin scope for our current operating ports.
            if label.startswith("west coast india to "):
                origins = ["mundra", "nhava sheva"]

            elif label.startswith(("east coast india (", "india (")):
                match = re.search(r"\(([^)]+)\)", label)
                if match:
                    origins = [
                        key(port)
                        for port in match.group(1).split("/")
                    ]

            db.executemany(
                "INSERT OR IGNORE INTO lane_origin_scope VALUES (?, ?)",
                [(label, origin) for origin in origins],
            )

    print("Lookup configuration saved.")
    print("Procurement and contact records unchanged.")


def lookup(pol, pod):
    with sqlite3.connect(
        DB_PATH.as_uri() + "?mode=ro", uri=True
    ) as db:
        db.row_factory = sqlite3.Row

        aliases = dict(db.execute(
            "SELECT alias_key, port_key FROM port_aliases"
        ))

        scopes = {
            tuple(row)
            for row in db.execute(
                "SELECT lane_key, pol_key FROM lane_origin_scope"
            )
        }

        rows = [
            dict(row)
            for row in db.execute("""
                SELECT * FROM procurement_entries
                ORDER BY source_row
            """)
        ]

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
        value = value or ""

        # Narrative or qualified coverage needs interpretation.
        markers = (
            "no service", "no rates", "no spot",
            "pending", "not verified", "via ",
            "@", "(", ")", ":",
        )

        if any(marker in value.casefold() for marker in markers):
            return set()

        return {
            canonical(port)
            for port in re.split(r"[,;\n]", value)
            if key(port)
        }

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

    configured_lanes = {scope[0] for scope in scopes}

    unconfigured = sorted({
        row["trade_lane"]
        for row in destination_rows
        if key(row["trade_lane"]) not in configured_lanes
    })

    result = {
        "pol": pol,
        "pod": pod,
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

    if not matching_lanes:
        result["next_action"] = (
            "Investigate port identity and origin/destination coverage; "
            "no applicable workbook match was found. "
            "This does not mean no service."
        )

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

        plan = lookup(args.pol, args.pod)

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