import os
import json
import imaplib
import email
from io import StringIO

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

print("RX Pickup Bot Started")

# ==========================================
# EMAIL CONFIG
# ==========================================

EMAIL_ID = os.environ["EMAIL_ID"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

# ==========================================
# GOOGLE SHEET LOGIN
# ==========================================

google_creds = json.loads(
    os.environ["GOOGLE_CREDENTIALS"]
)

creds = Credentials.from_service_account_info(
    google_creds,
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)

client = gspread.authorize(creds)

sheet = client.open(
    os.environ["GOOGLE_SHEET_NAME"]
).sheet1

print("Google Sheet Connected")

# ==========================================
# EXISTING CODES
# ==========================================

existing_codes = set()

try:

    data = sheet.get_all_values()

    for row in data[1:]:

        if len(row) > 1:

            code = str(row[1]).strip()

            if code:
                existing_codes.add(code)

except:
    pass

print(
    f"Existing Codes : {len(existing_codes)}"
)

# ==========================================
# IMAP LOGIN
# ==========================================

mail = imaplib.IMAP4_SSL(
    "webmail.responsexpress.com",
    993
)

mail.login(
    EMAIL_ID,
    EMAIL_PASSWORD
)

mail.select("INBOX")

status, messages = mail.search(
    None,
    'UNSEEN'
)

mail_ids = messages[0].split()

print(
    f"Unread Mails : {len(mail_ids)}"
)

# ==========================================
# PROCESS MAILS
# ==========================================

for mail_id in reversed(mail_ids):

    status, msg_data = mail.fetch(
        mail_id,
        "(RFC822)"
    )

    raw_email = msg_data[0][1]

    msg = email.message_from_bytes(
        raw_email
    )

    subject = str(
        msg["Subject"]
    )

    print(
        f"\nProcessing : {subject}"
    )

    if "Arrange the Pickup" not in subject:
        continue

    html_body = ""

    if msg.is_multipart():

        for part in msg.walk():

            if (
                part.get_content_type()
                == "text/html"
            ):

                html_body = part.get_payload(
                    decode=True
                ).decode(
                    errors="ignore"
                )

                break

    else:

        html_body = msg.get_payload(
            decode=True
        ).decode(
            errors="ignore"
        )

    if not html_body:
        continue

    tables = pd.read_html(
        StringIO(html_body)
    )

    if len(tables) == 0:

        print(
            "No Table Found"
        )

        continue

    df = tables[0]

    df.columns = df.iloc[0]

    df = df[1:].reset_index(
        drop=True
    )

    rows_to_add = []

    for _, row in df.iterrows():

        unique_code = str(
            row["Unique Code"]
        ).strip()

        if (
            unique_code == ""
            or unique_code == "nan"
        ):
            continue

        if unique_code in existing_codes:

            print(
                f"Duplicate : {unique_code}"
            )

            continue

        rows_to_add.append(
            row.fillna("").tolist()
        )

        existing_codes.add(
            unique_code
        )

    if rows_to_add:

        sheet.append_rows(
            rows_to_add,
            value_input_option="USER_ENTERED"
        )

        print(
            f"SUCCESS : {len(rows_to_add)} rows uploaded"
        )

    # mark mail read

    mail.store(
        mail_id,
        '+FLAGS',
        '\\Seen'
    )

mail.logout()

print("Completed")
