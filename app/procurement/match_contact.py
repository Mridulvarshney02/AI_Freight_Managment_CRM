import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "procurement.db"

# Contact-sheet label -> corresponding procurement-sheet label.
# These associations do not determine office responsibility.
MATCHES = {
    "Econship (additional contacts)": "Econship",
    "Arkas Line": "Arkas Line (Parekh Marine)",
    "Emirates Shipping Agencies (India) Pvt Ltd": "Emirates",
    "Messina (SOC)": "Messina",
    "Seatrade Shipping-UGL Line":
        "Samsara Group - Seatrade Shipping - UGL Line",
    "The shipping corporation of India Ltd.": "SCI",
    "UAFL Shipping Pvt Ltd (Agent for United Africa Feeder Line)":
        "United Africa Feeder Line (UAFL)",
}


def name_key(value):
    return " ".join(
        (value or "").replace("\xa0", " ").casefold().split()
    )


def main():
    connection = sqlite3.connect(
        DB_PATH.as_uri() + "?mode=rw",
        uri=True,
    )

    try:
        connection.execute("BEGIN")

        known_keys = {
            name_key(row[0])
            for row in connection.execute("""
                SELECT DISTINCT shipping_line_name
                FROM procurement_entries
            """)
        }

        mappings = {
            name_key(source): name_key(target)
            for source, target in MATCHES.items()
        }

        for target in mappings.values():
            if target not in known_keys:
                raise ValueError(
                    f"Procurement target is missing: {target}"
                )

        # Store these associations for future imports and lookups.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS shipping_line_aliases (
                alias_key TEXT PRIMARY KEY,
                procurement_match_key TEXT NOT NULL
            )
        """)

        for alias, target in mappings.items():
            existing = connection.execute("""
                SELECT procurement_match_key
                FROM shipping_line_aliases
                WHERE alias_key = ?
            """, (alias,)).fetchone()

            if existing and existing[0] != target:
                raise ValueError(
                    f"Conflicting saved association for: {alias}"
                )

            if existing is None:
                connection.execute("""
                    INSERT INTO shipping_line_aliases (
                        alias_key, procurement_match_key
                    ) VALUES (?, ?)
                """, (alias, target))

        contacts = connection.execute("""
            SELECT id, shipping_line_name, procurement_match_key
            FROM shipping_line_contacts
        """).fetchall()

        changed = 0

        for contact_id, source_name, existing_key in contacts:
            target = mappings.get(name_key(source_name))

            if target is None:
                continue

            if existing_key is not None and existing_key != target:
                raise ValueError(
                    f"Contact {contact_id} already has a different match."
                )

            if existing_key is None:
                connection.execute("""
                    UPDATE shipping_line_contacts
                    SET procurement_match_key = ?
                    WHERE id = ?
                """, (target, contact_id))
                changed += 1

        connection.commit()

        total, matched = connection.execute("""
            SELECT COUNT(*), COUNT(procurement_match_key)
            FROM shipping_line_contacts
        """).fetchone()

        print(f"Newly matched contact rows: {changed}")
        print(f"Total contact rows: {total}")
        print(f"Matched contact rows: {matched}")
        print(f"Unmatched contact rows: {total - matched}")

        print("\nRemaining unmatched labels:")
        for name, count in connection.execute("""
            SELECT shipping_line_name, COUNT(*)
            FROM shipping_line_contacts
            WHERE procurement_match_key IS NULL
            GROUP BY shipping_line_name
            ORDER BY shipping_line_name
        """):
            print(f"- {name}: {count} rows")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()