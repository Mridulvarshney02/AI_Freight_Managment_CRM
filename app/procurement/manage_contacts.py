import json
from uuid import uuid4
from sqlalchemy import text
from app.procurement.pg_database import get_engine

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
        raise ValueError("Source/change reason is required.")
    if any(not key(values.get(f)) for f in ("shipping_line_name", "office_location")):
        raise ValueError("Shipping line and office are required.")
    if not any(key(values.get(f)) not in ("", "-") for f in ("email_address", "contact_number")):
        raise ValueError("Provide email or phone.")
    with db.begin():
        db.execute(text("SELECT pg_advisory_xact_lock(26092602)"))
        known={key(r[0]) for r in db.execute(text("SELECT shipping_line_name FROM procurement.procurement_entries"))}
        aliases=dict(db.execute(text("SELECT alias_key, procurement_match_key FROM procurement.shipping_line_aliases")).tuples().all())
        carrier=key(values['shipping_line_name'])
        match=aliases.get(carrier,carrier)
        match=match if match in known else None
        old=None
        rows=db.execute(text("SELECT * FROM procurement.shipping_line_contacts")).mappings().all()
        for row in rows:
            if row['id']==contact_id:
                old=dict(row); continue
            if (row['procurement_match_key'] or key(row['shipping_line_name']))==(match or carrier) and all(
                key(row[f])==key(values.get(f)) for f in ('booking_agency','office_location','contact_person','email_address','contact_number')):
                raise ValueError(f"Duplicate of contact ID {row['id']}.")
        if contact_id is not None and old is None:
            raise ValueError("Contact ID does not exist.")
        data={f:values.get(f) for f in FIELDS}
        data['procurement_match_key']=match
        if old is None:
            # UUID source label prevents collisions with workbook rows and other editors.
            data.update(source_sheet='Manual '+str(uuid4()),source_row=1)
            cols=', '.join(data); params=', '.join(':'+f for f in data)
            contact_id=db.execute(text(f"INSERT INTO procurement.shipping_line_contacts ({cols}) VALUES ({params}) RETURNING id"),data).scalar_one()
        else:
            assignments=', '.join(f"{f}=:{f}" for f in data)
            db.execute(text(f"UPDATE procurement.shipping_line_contacts SET {assignments} WHERE id=:contact_id"),{**data,'contact_id':contact_id})
        new=dict(db.execute(text("SELECT * FROM procurement.shipping_line_contacts WHERE id=:id"),{'id':contact_id}).mappings().one())
        db.execute(text("""CREATE TABLE IF NOT EXISTS procurement.contact_changes (
            id SERIAL PRIMARY KEY, contact_id INTEGER NOT NULL, action TEXT NOT NULL,
            source_note TEXT NOT NULL, previous_record TEXT, new_record TEXT NOT NULL,
            changed_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP::text))"""))
        db.execute(text("""INSERT INTO procurement.contact_changes
            (contact_id,action,source_note,previous_record,new_record)
            VALUES (:id,:action,:source,:old,:new)"""),{
                'id':contact_id,'action':'update' if old else 'add','source':source.strip(),
                'old':json.dumps(old,ensure_ascii=False) if old else None,'new':json.dumps(new,ensure_ascii=False)})
    return contact_id,match


def main():
    with get_engine().connect() as db:

        action = input("Action (list/add/update): ").strip().lower()

        if action == "list":
            search = key(input(
                "Shipping-line name filter (blank = all): "
            ))

            for row in db.execute(text("SELECT * FROM procurement.shipping_line_contacts ORDER BY id")).mappings():
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

            row = db.execute(text("SELECT * FROM procurement.shipping_line_contacts WHERE id = :id"), {"id": contact_id}).mappings().first()

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

        db.rollback()  # End read transaction before the atomic update.
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
    except ValueError as exc:
        raise SystemExit(f"Not saved: {exc}")