import pandas as pd
from app.database import SessionLocal
from app.models import Query


def read_excel(file_path: str):
    """
    Read an Excel file and return a pandas DataFrame.
    """
    df = pd.read_excel(file_path)
    # Clean column names
    df.columns = df.columns.str.replace("\xa0", "", regex=False).str.strip()

    return df


def convert_to_boolean(value):
    """
    Convert Excel values like Y/N into Python booleans.
    """

    if value is None:
        return False
    
    if str(value).strip().lower() == "y":
        return True

    return False


def clean_dataframe(df):
    # Drop unwanted columns
    df = df.drop(
        columns=["S.NO", "RATE MATCHED", "REMARKS.1", "Unnamed: 13"],
        errors="ignore",
    )

    # Rename columns to match our model
    df = df.rename(
        columns={
            "COMPANY NAME": "company_name",
            "POL": "origin_port",
            "POD": "destination_port",
            "Cont Type": "container_type",
            "QUERY RECVD": "query_received",
            "QUOTE SHARED": "quote_shared",
            "NEXT ACTION": "next_action",
            "NEXT ACTION DATE": "next_action_date",
            "REMARKS": "remarks",
            "Shipment Close": "shipment_status",
        }
    )
    for column in df.select_dtypes(include=["object", "string"]).columns:
        df[column] = (
            df[column].astype("string").str.replace("\xa0", "", regex=False).str.strip()
        )

    # Convert Y/N to True/False
    df["query_received"] = df["query_received"].apply(convert_to_boolean)
    df["quote_shared"] = df["quote_shared"].apply(convert_to_boolean)

    # Convert dates
    df["next_action_date"] = pd.to_datetime(
        df["next_action_date"], format="%d.%m.%Y", errors="coerce"
    ).dt.date
    # Replace NaN with None
    df = df.where(pd.notnull(df), None)
    return df

def clean_null(value):
    """Convert pandas missing values to Python None."""
    if pd.isna(value):
        return None
    return value

def save_to_database(df):

    db = SessionLocal()

    try:

        db.query(Query).delete()
        db.commit()

        for _, row in df.iterrows():

            # Step 1: Determine validation status
            status = "Valid"

            required_fields = [
                "company_name",
                "origin_port",
                "destination_port",
                "container_type",
            ]

            if any(pd.isna(row[field]) for field in required_fields):
                status = "Needs Review"

            # Step 2: Create Query object
            query = Query(
                company_name=clean_null(row["company_name"]),
                origin_port=clean_null(row["origin_port"]),
                destination_port=clean_null(row["destination_port"]),
                container_type=clean_null(row["container_type"]),
                query_received=row["query_received"],
                quote_shared=row["quote_shared"],
                next_action=clean_null(row["next_action"]),
                next_action_date=clean_null(row["next_action_date"]),
                remarks=clean_null(row["remarks"]),
                shipment_status=clean_null(row["shipment_status"]),
                validation_status=status,
            )

            # Step 3: Add to database
            db.add(query)

        db.commit()

    except Exception as e:
        db.rollback()
        print(e)

    finally:
        db.close()


if __name__ == "__main__":
    df = read_excel("/Users/mridul/Desktop/AI_freight_system/data/freight_queries.xlsx")

    df = clean_dataframe(df)
    save_to_database(df)
