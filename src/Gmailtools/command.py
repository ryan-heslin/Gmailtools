#!/usr/bin/python3

import json
import sys

import argparse as ap

from Gmailtools import utils

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

    for message in response:
        gmail_service.users().messages().modify(
            userId="me", id=message["id"], body={"removeLabelIds": ["UNREAD"]}
        ).execute()
    print("All emails marked read")


# Configure for plaintext decoding


def query_emails(new_args=None, prev_args=None):
    """
    Implement query_emails command, which retrieves user query_emails
    matching search parameters. Parses command-line arguments
    by default, but may be called with additional arguments, or optionally a dict of previously used arguments to limit the search.

    :param new_args: List of command-line arguments and values, parsed in addition to command-line arguments
    :type: new_args: list, optional
    :param prev_args: [dict] Dict of argument-value pairs representing a previous search's parameters. Old string arguments are concatenated with any new specifications of the same arguments, non-string types are replaced, and any not specified by the new search are retained.
    :type: prev_args: dict, optional
    """

    from Gmailtools import utils
    from os.path import abspath

    # Configure for plaintext decoding
    gmail_service = utils.authenticate()

    parser = ap.ArgumentParser(description="""Specify email search parameters""")
    subparsers = parser.add_subparsers(
        title="Subcommands",
        description="Subcommands to apply to retrieved emails",
        dest="subcommand",
        help="Subcommands",
        required=False,
    )

    # Subparsers
    parser_download = subparsers.add_parser(
        "download_attachments",
        help="Download attached files in a specified directory",
        aliases=["dl"],
    )
    parser.set_defaults(print_emails=True)
    parser_store = subparsers.add_parser(
        "store_emails",
        help="Save retrieved emails to a specified JSON file",
        aliases=["se"],
    )
    parser_print = subparsers.add_parser(
        "print_emails", help="Print formatted emails to stdout", aliases=["pe"]
    )
    parser_print.set_defaults(func=utils.parse_emails)
    parser_store.set_defaults(func=utils.parse_emails)
    parser_download.set_defaults(func=utils.parse_emails)
    # subparsers.set_defaults(subcommand="print_emails")

    parser_download.add_argument(
        "-d",
        "--download_dir",
        help="Directory in which to download email attachments. Must be a valid absolute or relative path. Defaults to working directory.",
        default=abspath("."),
        action=classes.DirAction,
        nargs="?",
    )

    parser_download.add_argument(
        "-v",
        "--verbose",
        help="""Print message describing command actions""",
        action="store_true",
    )

    parser_download.add_argument(
        "--force",
        help="Overwrite existing files with the same names as download attachments",
        action="store_true",
    )
    parser_store.add_argument(
        "--output",
        type=ap.FileType("w+", errors="replace"),
        help="Output file to write to",
    )
    parser_store.add_argument(
        "-v",
        "--verbose",
        help="""Print message describing command actions""",
        action="store_true",
    )
    parser_print.add_argument(
        "--await",
        action="store_true",
        help="""Await further input after printing emails""",
    )

    search_args_parser = ap.ArgumentParser(description="Search arguments")
    search_args_parser.add_argument(
        "-f",
        "--from",
        action=classes.QueryAction,
        nargs="*",
        help="""Senders to query for""",
    )
    search_args_parser.add_argument(
        "-t",
        "--to",
        action=classes.QueryAction,
        nargs="*",
        help="""Receivers to query for""",
    )
    search_args_parser.add_argument(
        "-w",
        "--word",
        action=classes.QueryAction,
        nargs="*",
        help="""Words to query for""",
    )
    search_args_parser.add_argument(
        "-l",
        "--label",
        action=classes.QueryAction,
        nargs="*",
        help="""Labels to query for""",
    )
    search_args_parser.add_argument(
        "-s",
        "--subject",
        action=classes.QueryAction,
        nargs="*",
        help="""Words in the subject line to query for""",
    )
    search_args_parser.add_argument(
        "--filename",
        action=classes.QueryAction,
        nargs="?",
        help="""Attachment file name or extension to search for""",
    )
    search_args_parser.add_argument(
        "-b",
        "--before",
        action=classes.QueryAction,
        nargs="?",
        help="""Date before (as YYYY/DD/MM or MM/DD/YYYY)""",
    )
    search_args_parser.add_argument(
        "-a",
        "--after",
        action=classes.QueryAction,
        nargs="?",
        help="""Date after (as YYYY/DD/MM or MM/DD/YYYY)""",
    )
    search_args_parser.add_argument(
        "-c",
        "--category",
        action=classes.QueryAction,
        nargs="?",
        help="""Email category""",
    )
    search_args_parser.add_argument(
        "-i",
        "--ids",
        action=classes.QueryAction,
        nargs="*",
        help="""RFC message IDs to include""",
    )
    search_args_parser.add_argument(
        "-e",
        "--extra",
        nargs="?",
        help="""Additional query (quoted) to append to search""",
    )
    # 500 is API max
    search_args_parser.add_argument(
        "-m",
        "--max_emails",
        type=int,
        nargs="?",
        help="Maximum number of emails to return",
        default=500,
        action=classes.MaxAction,
    )

    search_args_parser.add_argument(
        "-o", "--or", action="store_true", help="""Use OR instead of AND combinator"""
    )
    # breakpoint()
    if new_args:
        sub_args, search_args = parser.parse_known_args(new_args)
    else:
        sub_args, search_args = parser.parse_known_args()

    # Only retain old search args; old subcommand args assumed irrelevant
    # TODO: Update dict of parsed search args wiith previous, combining shared keys (usually list extending)

    # Insert additional arguments passed directly to function. Invoked if user does a refined search of an initial search.
    # args = utils.insert_args(extra_args) if extra_args else args
    search_args = vars(search_args_parser.parse_args(search_args))
    if prev_args:
        # breakpoint()
        prev_args = classes.PartialUpdateDict(prev_args)
        prev_args.update(search_args)
        search_args = prev_args

    sub_args.func(gmail_service, search_args, vars(sub_args))
