#!/usr/bin/python3
import utils

utils.set_wd_to_file(__file__)
gmail_service = utils.authenticate()
response = utils.page_response(gmail_service, q="in:inbox is:unread")
ids = [message["id"] for message in response]

for ID in ids:
    gmail_service.users().messages().modify(
        userId="me", id=ID, body={"removeLabelIds": ["UNREAD"]}
    ).execute()
print("All emails marked read")
