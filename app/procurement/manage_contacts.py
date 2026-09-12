import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "procurement.db"

FIELDS = {
    "shipping_line_name": "Shipping line",
    "booking_agency": "Agency",
    "office_location": "Office location",
    "contact_person": "Contact person",
    "email_address": "Email address",
    "contact_number": "Phone number",
    "additional_information": "Notes",
}


def key(value):
    return " ".join(
        (value or "").replace("\xa0", " ").casefold().split()
    )


def save_contact(db, values, source, contact_id=None):
    if not source.strip():
        raise ValueError("A source or reason for the change is required.")

    for field in ("shipping_line_name", "office_location"):
        if not key(values[field]):
            raise ValueError(f"Missing {FIELDS[field]}.")

    if not any(
        key(values[field]) not in ("", "-")
        for field in ("email_address", "contact_number")
    ):
        raise ValueError("Provide an email address or phone number.")

    db.execute("BEGIN IMMEDIATE")

    try:
        old = None

        if contact_id is not None:
            row = db.execute(
                "SELECT * FROM shipping_line_contacts WHERE id = ?",
                (contact_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Contact ID does not exist.")

            old = dict(row)

        known = {
            key(row[0])
            for row in db.execute("""
                SELECT DISTINCT shipping_line_name
                FROM procurement_entries
            """)
        }

        aliases = dict(db.execute("""
            SELECT alias_key, procurement_match_key
            FROM shipping_line_aliases
        """))

        carrier = key(values["shipping_line_name"])
        target = aliases.get(carrier, carrier)
        match = target if target in known else None

        identity_fields = (
            "booking_agency",
            "office_location",
            "contact_person",
            "email_address",
            "contact_number",
        )

        for row in db.execute("SELECT * FROM shipping_line_contacts"):
            if row["id"] == contact_id:
                continue

            existing_carrier = (
                row["procurement_match_key"]
                or key(row["shipping_line_name"])
            )

            if (
                existing_carrier == (match or carrier)
                and all(
                    key(row[field]) == key(values[field])
                    for field in identity_fields
                )
            ):
                raise ValueError(
                    f"Duplicate of contact ID {row['id']}; "
                    "update that record instead."
                )

        db.execute("""
            CREATE TABLE IF NOT EXISTS contact_changes (
                id INTEGER PRIMARY KEY,
                contact_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                source_note TEXT NOT NULL,
                previous_record TEXT,
                new_record TEXT NOT NULL,
                changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        if old is None:
            number = db.execute("""
                SELECT COALESCE(MAX(source_row), 0) + 1
                FROM shipping_line_contacts
                WHERE source_sheet = 'Manual entry'
            """).fetchone()[0]

            columns = [
                *FIELDS,
                "source_sheet",
                "source_row",
                "procurement_match_key",
            ]
            payload = [
                values[field] for field in FIELDS
            ] + ["Manual entry", number, match]

            placeholders = ", ".join("?" for _ in columns)

            cursor = db.execute(
                f"INSERT INTO shipping_line_contacts "
                f"({', '.join(columns)}) VALUES ({placeholders})",
                payload,
            )
            contact_id = cursor.lastrowid

        else:
            assignments = ", ".join(
                f"{field} = ?" for field in FIELDS
            )

            db.execute(
                f"UPDATE shipping_line_contacts SET {assignments}, "
                "procurement_match_key = ? WHERE id = ?",
                [values[field] for field in FIELDS]
                + [match, contact_id],
            )

        new = dict(db.execute(
            "SELECT * FROM shipping_line_contacts WHERE id = ?",
            (contact_id,),
        ).fetchone())

        db.execute("""
            INSERT INTO contact_changes (
                contact_id, action, source_note,
                previous_record, new_record
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            contact_id,
            "update" if old else "add",
            source.strip(),
            json.dumps(old, ensure_ascii=False) if old else None,
            json.dumps(new, ensure_ascii=False),
        ))

        db.commit()
        return contact_id, match

    except Exception:
        db.rollback()
        raise


def main():
    with sqlite3.connect(
        DB_PATH.as_uri() + "?mode=rw",
        uri=True,
    ) as db:
        db.row_factory = sqlite3.Row

        action = input("Action (list/add/update): ").strip().lower()

        if action == "list":
            search = key(input(
                "Shipping-line name filter (blank = all): "
            ))

            for row in db.execute(
                "SELECT * FROM shipping_line_contacts ORDER BY id"
            ):
                if search in key(row["shipping_line_name"]):
                    print(
                        row["id"],
                        row["shipping_line_name"],
                        row["office_location"],
                        row["contact_person"],
                        row["email_address"],
                        row["contact_number"],
                        sep=" | ",
                    )
            return

        if action not in ("add", "update"):
            raise ValueError("Choose list, add or update.")

        contact_id = None
        old = {}

        if action == "update":
            contact_id = int(input("Contact ID: "))

            row = db.execute(
                "SELECT * FROM shipping_line_contacts WHERE id = ?",
                (contact_id,),
            ).fetchone()

            if row is None:
                raise ValueError("Contact ID does not exist.")

            old = dict(row)
            print("Blank keeps the current value; /clear removes it.")

        values = {}

        for field, label in FIELDS.items():
            suffix = f" [{old.get(field) or ''}]" if old else ""
            value = input(f"{label}{suffix}: ").strip()

            if value == "/clear":
                values[field] = None
            elif not value and old:
                values[field] = old.get(field)
            else:
                values[field] = value or None

        source = input(
            "Source/change reason (include your name): "
        )

        contact_id, match = save_contact(
            db, values, source, contact_id
        )

        print(f"Saved contact ID {contact_id}.")
        print(
            "Procurement match:",
            match or "Unmatched; stored as contact-only",
        )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, sqlite3.Error) as exc:
        raise SystemExit(f"Not saved: {exc}")