#!/usr/bin/python3

import json
import sys

from Gmailtools import utils
import argparse as ap

from Gmailtools import classes

"""Functions containing command-line programs to use API"""


def assign_label():

    parser = ap.ArgumentParser(
        description="""Specify name for label and file of addresses to filter for"""
    )
    parser.add_argument("name", type=str, help="Label to assign")
    parser.add_argument(
        "file",
        type=str,
        help="Path to file containing email addresses to assign to label",
    )
    parser.add_argument(
        "-j",
        "--json-index",
        nargs="*",
        default=[],
        help="""One or more keys, in the sequence needed to retrieve a list of email addresses in 
            the JSON provided to the \"file\" argument, (e.g., \"students\" \"emails\" if the desired list of emails is keyed to \"emails\" within \"students.\" Defaults to the empty list (corresponding to a flat JSON with no nested keys). """,
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=False,
        help="""Flag indicating whether to overwrite an existing label by the specified name. Default False.""",
    )
    args = vars(parser.parse_args())

    # if args["file"] is None and args["json_index"] != []:
    # print(f"JSON index {args['json_index']} specified, but no file specified")
    # sys.exit()

    # Create from query
    try:
        with open(args["file"]) as f:
            full = json.load(f)
    except Exception as e:
        print(f"Error reading {args['file']!r} : {e} ")
        sys.exit()
    try:
        emails = utils.reduce_keys(full, args["json_index"])
    except KeyError as e:
        print(f"Key error parsing JSON file: {e} ")
        sys.exit()

    gmail_service = utils.authenticate()
    mapping = utils.label_decode(gmail_service, id_key=False)

    # Handle preexisting label
    if args["name"] in mapping.keys():
        if not args["force"]:
            print(f"Label {args['name']!r} already in use, but overwriting is disabled")
            sys.exit()
        # Delete preexisting label
        utils.delete_label(gmail_service, mapping[args["name"]])
    # If label already exists, get id; otherwise create and get id
    label_id = (
        gmail_service.users()
        .labels()
        .create(userId="me", body={"name": args["name"]})
        .execute()["id"]
    )

    labels = "{" + " ".join(f"from: {x}" for x in emails) + "}"

    Filter = {"criteria": {"from": labels}, "action": {"addLabelIds": [label_id]}}
    try:
        result = (
            gmail_service.users()
            .settings()
            .filters()
            .create(userId="me", body=Filter)
            .execute()
        )
    except Exception as e:
        print(f"Error creating label: {e}")
        sys.exit()
    print(f"Created label {args['name']!r}")


def mark_read():
    gmail_service = utils.authenticate()
    response = utils.page_response(gmail_service, q="in:inbox is:unread")
    ids = [message["id"] for message in response]

    for ID in ids:
        gmail_service.users().messages().modify(
            userId="me", id=ID, body={"removeLabelIds": ["UNREAD"]}
        ).execute()
    print("All emails marked read")


# Configure for plaintext decoding


def query_emails():
    gmail_service = utils.authenticate()

    parser = ap.ArgumentParser(description="""Specify email search parameters""")
    parser.add_argument(
        "-f",
        "--from",
        action=classes.QueryAction,
        type=str,
        nargs="*",
        help="""Senders to query for""",
    )
    parser.add_argument(
        "-t",
        "--to",
        action=classes.QueryAction,
        nargs="*",
        help="""Receivers to query for""",
    )
    parser.add_argument(
        "-w",
        "--word",
        action=classes.QueryAction,
        nargs="*",
        help="""Words to query for""",
    )
    parser.add_argument(
        "-l",
        "--label",
        action=classes.QueryAction,
        nargs="*",
        help="""Labels to query for""",
    )
    parser.add_argument(
        "-s",
        "--subject",
        action=classes.QueryAction,
        nargs="*",
        help="""Words in the subject line to query for""",
    )
    parser.add_argument(
        "--filename",
        action=classes.QueryAction,
        nargs="*",
        help="""Attachment file name or extension""",
    )
    parser.add_argument(
        "-b",
        "--before",
        action=classes.QueryAction,
        nargs="?",
        help="""Date before (as YYYY/DD/MM or MM/DD/YYYY)""",
    )
    parser.add_argument(
        "-a",
        "--after",
        action=classes.QueryAction,
        nargs="?",
        help="""Date after (as YYYY/DD/MM or MM/DD/YYYY)""",
    )
    parser.add_argument(
        "-c",
        "--category",
        action=classes.QueryAction,
        nargs="?",
        help="""Email category""",
    )
    parser.add_argument(
        "-e",
        "--extra",
        nargs="?",
        help="""Additional query (quoted) to append to search""",
    )
    # 500 is API max
    parser.add_argument(
        "-m",
        "--max_emails",
        type=int,
        nargs="?",
        help="Maximum number of emails to return",
        default=500,
        action=classes.MaxAction,
    )
    parser.add_argument(
        "-o",
        "--outfile",
        nargs="?",
        action=classes.OutfileAction,
        help="Output file to write to",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Flag to suppress printing"
    )
    parser.add_argument(
        "-O", "--or", action="store_true", help="""Use OR instead of AND combinator"""
    )

    args = vars(parser.parse_args())
    # Exit if no arguments are supplied
    if all(arg is None or type(arg) is bool for arg in args.values()):
        sys.exit("Error: No arguments provided")
    max_emails = args.pop("max_emails")
    quiet = args.pop("quiet")

    # Choose between OR or AND for search terms
    combinator = " " if (OR := args.pop("or")) else " AND "
    args = {k: v for k, v in args.items() if v is not None}
    outfile = args.pop("outfile") if "outfile" in args.keys() else None
    request = ("{" * OR) + combinator.join(args.values()) + ("}" * OR)

    messages = utils.page_response(
        gmail_service, max_emails=max_emails, userId="me", q=request
    )

    if len(messages) == 0:
        sys.exit(f"No messages matched query {request}")

    # Retrieve message texts
    raw_messages = [
        gmail_service.users()
        .messages()
        .get(userId="me", id=message["id"])
        .execute()["payload"]
        for message in messages
    ]
    breakpoint()

    parsed_messages = dict([utils.parse_message(message) for message in raw_messages])
    if not quiet:
        for message in parsed_messages.values():
            utils.print_message(message)
    if outfile:
        with open(outfile, "w+") as f:
            json.dump(parsed_messages, f)
