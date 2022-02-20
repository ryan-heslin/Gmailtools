#!/usr/bin/python3

import json
import sys
import utils

infile = sys.argv[1]
label_name = sys.argv[2]

utils.set_wd_to_file(__file__)
gmail_service = utils.authenticate("./credentials.json")

# If label already exists, get id; otherwise create and get id
try:
    label_id = utils.label_decode(gmail_service)[label_name]
except KeyError:
    print(f"Creating label " '{label_name}"')
    label_id = (
        gmail_service.users()
        .labels()
        .create(userId="me", body={"name": label_name})
        .execute()["id"]
    )

# Create from query
with open(infile) as file:
    labels = "{" + " ".join(["from: " + x for x in json.load(file)["email"]]) + "}"

Filter = {"criteria": {"from": labels}, "action": {"addLabelIds": [label_id]}}
try:
    result = (
        gmail_service.users()
        .settings()
        .filters()
        .create(userId="me", body=Filter)
        .execute()
    )
except:
    print("error")
    sys.exit()
print(f"Created filter {result.get('id')}")
