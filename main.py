import os
import json
import imaplib
import email
import requests
from io import StringIO
from email.utils import parsedate_to_datetime

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

def send_telegram(message):
    try:
        token = os.environ["TELEGRAM_BOT_TOKEN"]

        chat_ids = os.environ[
            "TELEGRAM_CHAT_IDS"
        ].split(",")

        for chat_id in chat_ids:

            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={
                    "chat_id": chat_id.strip(),
                    "text": message,
                    "parse_mode": "Markdown"
                },
                timeout=20
            )

    except Exception as e:
        print(f"Telegram Error : {e}")


print("===== VERSION 2 (PRO-MARKDOWN) =====")
print("RX Pickup Bot Started")

# ==========================================
# CONFIG
# ==========================================

EMAIL_ID = os.environ["EMAIL_ID"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
SHEET_NAME = os.environ["GOOGLE_SHEET_NAME"]

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
    SHEET_NAME
).sheet1

print("Google Sheet Connected")

# ==========================================
# EXISTING UNIQUE CODES
# ==========================================

existing_codes = set()

try:
    data = sheet.get_all_values()
    for row in data[1:]:
        if len(row) > 1:
            code = str(row[1]).strip()
            if code:
                existing_codes.add(code)
except Exception as e:
    print(f"Code Load Error : {e}")

print(f"Existing Codes : {len(existing_codes)}")

# ==========================================
# IMAP LOGIN
# ==========================================

mail = imaplib.IMAP4_SSL(
    "smartmail.bookmyhost.com",
    993
)

mail.login(
    EMAIL_ID,
    EMAIL_PASSWORD
)

print("IMAP Login Success")

mail.select("INBOX")

status, messages = mail.search(
    None,
    'UNSEEN'
)

mail_ids = messages[0].split()

print(f"Unread Mails : {len(mail_ids)}")

# ==========================================
# PROCESS MAILS
# ==========================================

for mail_id in reversed(mail_ids):
    try:
        status, msg_data = mail.fetch(
            mail_id,
            "(RFC822)"
        )

        raw_email = msg_data[0][1]

        msg = email.message_from_bytes(
            raw_email
        )

        subject = str(
            msg.get("Subject", "")
        )

        email_datetime_obj = parsedate_to_datetime(msg.get("Date"))
        # Telegram format: 31-May-2026 09:11 PM
        tele_date_format = email_datetime_obj.strftime("%d-%b-%Y %I:%M %p")
        
        # Sheet format
        email_datetime = email_datetime_obj.strftime("%d-%m-%Y %H:%M:%S")
        
        print(f"\nProcessing : {subject}")

        if "Arrange the Pickup" not in subject:
            continue

        html_body = ""

        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_body = part.get_payload(
                        decode=True
                    ).decode(errors="ignore")
                    break
        else:
            html_body = msg.get_payload(
                decode=True
            ).decode(errors="ignore")

        if not html_body:
            print("No HTML Body Found")
            continue

        tables = pd.read_html(
            StringIO(html_body)
        )

        print(f"Tables Found : {len(tables)}")

        if len(tables) == 0:
            continue

        df = tables[0]
        df.columns = df.iloc[0]
        df = df[1:].reset_index(drop=True)

        rows_to_add = []
        
        # --- PRO STATISTICS COUNTERS ---
        total_rows = 0
        duplicate_count = 0
        unique_codes_processed = []

        for _, row in df.iterrows():
            if "Unique Code" not in row:
                continue

            unique_code = str(
                row["Unique Code"]
            ).strip()

            if unique_code == "" or unique_code.lower() == "nan":
                continue

            total_rows += 1

            if unique_code in existing_codes:
                print(f"Duplicate : {unique_code}")
                duplicate_count += 1
                continue

            new_row = [
                email_datetime
            ]
            
            new_row.extend(
                row.fillna("").tolist()
            )
            
            rows_to_add.append(new_row)
            existing_codes.add(unique_code)
            unique_codes_processed.append(unique_code)
            
        # FOR LOOP KHATAM
        
        if rows_to_add:
            sheet.append_rows(
                rows_to_add,
                value_input_option="USER_ENTERED"
            )
        
            print(f"SUCCESS : {len(rows_to_add)} rows uploaded")
            
            # --- SARE CODES VISIBLE + ONE-TAP COPY LOGIC ---
            total_unique_in_mail = total_rows - duplicate_count
            new_records_count = len(rows_to_add)
            
            # Format all codes with backticks for monospace copy feature
            all_codes_formatted = [f"`{code}`" for code in unique_codes_processed]
            codes_text = "\n".join(all_codes_formatted)
                
            pro_message = (
                f"🚀 SUPER URGENT WH BOT\n"
                f"✅ NEW PICKUPS ADDED\n\n"
                f"📧 Subject\n"
                f"{subject}\n\n"
                f"📅 Email Date\n"
                f"{tele_date_format}\n\n"
                f"📈 Statistics\n"
                f"├─ Total Rows      : {total_rows}\n"
                f"├─ Unique IDs      : {total_unique_in_mail}\n"
                f"├─ Duplicate IDs   : {duplicate_count}\n"
                f"├─ New Records     : {new_records_count}\n"
                f"└─ Status          : SUCCESS\n\n"
                f"📦 Pickup Codes ({new_records_count})\n"
                f"{codes_text}\n\n"
                f"🤖 RX Pickup Automation"
            )
        
            send_telegram(pro_message)
        else:
            print("No New Records")

        # Mark mail as read
        mail.store(
            mail_id,
            '+FLAGS',
            '\\Seen'
        )
        print("Mail Marked Read")

    except Exception as e:
        print(f"Mail Error : {e}")
    
        send_telegram(
            f"❌ Pickup Bot Error\n\n{e}"
        )
        
