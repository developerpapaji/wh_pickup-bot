import os
import json
import imaplib

print("RX Pickup Bot Started")

EMAIL_ID = os.environ["EMAIL_ID"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
SHEET_NAME = os.environ["GOOGLE_SHEET_NAME"]

print("Connecting IMAP...")

mail = imaplib.IMAP4_SSL(
"smartmail.bookmyhost.com",
993
)

mail.login(
EMAIL_ID,
EMAIL_PASSWORD
)

mail.select("INBOX")

status, data = mail.search(
None,
'UNSEEN'
)

ids = data[0].split()

print(f"Unread Mails : {len(ids)}")

mail.logout()

print("Completed")
