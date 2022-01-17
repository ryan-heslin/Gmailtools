#!/usr/bin/python3

import sys
import utils
import argparse as ap
import json
import classes
from os.path import join

# Configure for plaintext decoding

# utils.set_wd_to_file(__file__)
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
    "-w", "--word", action=classes.QueryAction, nargs="*", help="""Words to query for"""
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
    nargs="?",
    help="""Attachment file name or extension to search for""",
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
    "-c", "--category", action=classes.QueryAction, nargs="?", help="""Email category"""
)
parser.add_argument(
    "-e", "--extra", nargs="?", help="""Additional query (quoted) to append to search"""
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
    type=ap.FileType("w+", errors="replace"),
    nargs="?",
    help="Output file to write to",
)
parser.add_argument(
    "-d",
    "--download-dir",
    help="Directory in which to download email attachments. Must be a valid absolute or relative path.",
    action=classes.DirAction,
    nargs="?",
)
parser.add_argument(
    "-q", "--quiet", action="store_true", help="Flag to suppress printing"
)
parser.add_argument(
    "-O", "--or", action="store_true", help="""Use OR instead of AND combinator"""
)

args = vars(parser.parse_args())
if args == {} or all(arg is None for arg in args.values()):
    sys.exit("Error: No arguments provided")
max_emails = args.pop("max_emails")
quiet = args.pop("quiet")
# download = args.pop("download")

# Choose between OR or AND for search terms
combinator = " " if (OR := args.pop("or")) else " AND "
outfile = args.pop("outfile")
download_dir = args.pop("download_dir")
args = {k: v for k, v in args.items() if v is not None}
request = ("{" * OR) + " ".join(args.values()) + ("}" * OR)

messages = utils.page_response(
    gmail_service, max_emails=max_emails, userId="me", q=request
)

if len(messages) == 0:
    sys.exit(f"No messages matched query {request}")

# Extract each payload, yielding MessagePart object
raw_messages = [
    gmail_service.users()
    .messages()
    .get(userId="me", id=message["id"])
    .execute()["payload"]
    for message in messages
]
parsed_messages = dict(
    [utils.parse_message(gmail_service, message) for message in raw_messages]
)
if not quiet:
    for message in parsed_messages.values():
        utils.print_message(message)
        utils.print_sep()
# breakpoint()
if outfile:
    json.dump(parsed_messages, outfile)

# Download attachments to specified directory
if download_dir:
    for message in parsed_messages:
        for k, v in message.attachments:
            path = join(download_dir, k)
            with open(path, "wb") as f:
                f.write(v)
