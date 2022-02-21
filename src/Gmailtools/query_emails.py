#!/usr/bin/python3

import sys
import utils
import argparse as ap
import json
import classes
from os.path import join, abspath
import constants

# Configure for plaintext decoding

# utils.set_wd_to_file(__file__)
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
    "--await", action="store_true", help="""Await further input after printing emails"""
)

sub_args, search_args = parser.parse_known_args()
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
    "-w", "--word", action=classes.QueryAction, nargs="*", help="""Words to query for"""
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
    "-c", "--category", action=classes.QueryAction, nargs="?", help="""Email category"""
)
search_args_parser.add_argument(
    "-e", "--extra", nargs="?", help="""Additional query (quoted) to append to search"""
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
# Insert additional arguments passed directly to function. Invoked if user does a refined search of an initial search.
# args = utils.insert_args(extra_args) if extra_args else args
search_args = search_args_parser.parse_args(search_args)

sub_args.func(gmail_service, vars(search_args), vars(sub_args))
