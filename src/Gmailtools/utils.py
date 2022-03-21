from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from io import TextIOWrapper
from functools import reduce

from requests.models import HTTPError

import mimetypes

import os
import datetime
import base64
import email
import json
from sys import exit

from Gmailtools import constants

from Gmailtools import classes
from Gmailtools import command

# Largely copied from Google's quickstart guide


def authenticate(
    scopes=constants.SCOPES,
    token_path=os.path.expanduser(os.environ.get("TOKEN_PATH", "~/token.json")),
    credentials_path=os.path.expanduser(
        os.environ.get("CREDENTIALS_PATH", "~/credentials.json")
    ),
    write_token=False,
):
    """
    Creates a Gmail API client with the specified authorization scopes. First looks for a token
    containing the authorization for a previous run. If this does not exist (as on the first run of an
    application), instead looks for a file with application credentials.

    :param scopes: List of scopes for which to authorize the application, defaults to constants.SCOPES. This global constant contains almost all possible scopes, so you should probably specify only those you need.
    :type scopes: List[str], optional
    :param token_path: Path to a JSON file containing authorization credentials saved from a previous use. Defaults to the environment variable TOKEN_PATH; if unset, defaults to :code:`os.path.expanduser("~/token.json")`.
    :type token_path: str, optional
    :param credentials_path: Path to a JSON file containing authorization credentials, defaults to the environment variable CREDENTIALS_PATH; if unset, defaults to :code:`os.path.expanduser("~/credentials.json")`.
    :type credentials_path: str, optional
    :param write_token: Indicates whether to save an authorization token for future use to :code:`token_path` if it does not already exist, default False.
    :type write_token: bool
    """
    creds = None
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise IOError(f"{credentials_path} does not exist")
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, scopes=None
            )  # changed to None
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        if write_token and not os.path.exists(token_path):
            try:
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"Error writing token: {e}")
    service = build("gmail", "v1", credentials=creds)
    return service


def set_wd_to_file(file):
    """Set working directory to the directory containing the current file"""
    current_wd = os.path.abspath(file)
    os.chdir(os.path.dirname(current_wd))


def list_filters(service):
    """List all filters active in a user account"""
    return service.users().settings().filters().list(userId="me").execute()


def label_decode(service, id_key=True):
    """Get a mapping of label IDs to names (the user-facing label names)"""
    labels = service.users().labels().list(userId="me").execute()["labels"]
    # Ensure correct key-value order (defaults to ID as key)
    k, v = ("id", "name") if id_key else ("name", "id")
    return {label[k]: label[v] for label in labels}


def delete_label(service, label_id):
    """Delete a label from its ID"""
    try:
        service.users().labels().delete(userId="me", id=label_id).execute()
    except HTTPError as e:
        print(f"Error deleting label: {e}. Make sure the label if {label_id} exists")


def append_category(lst, category, joiner=" ", sep=":", surround="", group_or=False):
    """Helper to transform a list of strings into a string of key-value pairs with separating and surrounding fields."""
    lst = [lst] if type(lst) is str else lst
    out = joiner.join([f"{surround}{category}{sep}{x}{surround}" for x in lst])
    if group_or:
        out = "{" + out + "}"
    return out


def validate_before_present(date_string, formats):
    """
    Tries to parse a date string by various formats, checking each until it
    finds one before the current system date.

    :param date_string str: String representing a date to validate.
    :param formats list [str]: Date string formats to try parsing
    :raises ValueError: Raised if no format parses, or all that do parse are not before the current date
    """
    for fmt in formats:
        try:
            parsed = datetime.datetime.strptime(date_string, fmt)
            if datetime.datetime.now() >= parsed:
                return True
        except:
            pass
    raise ValueError(f"Date argument {date_string!r} did not parse or is in the future")


def get_message(gmail_service, userId="me", **kwargs):
    """Retrieve a message given a user ID and message ID"""
    return gmail_service.users().messages().list(userId=userId, **kwargs).execute()


def parse_message(gmail_service, messages):
    """Traverse message to extract sender, recipient, date, and text"""
    for message in messages:
        header = extract_header(message["headers"])
        parsed = extract_fields(gmail_service, message=message, message_id=header["id"])
        yield {**header, **parsed}


def extract_fields(gmail_service, message, message_id):
    """Recurses through message parts until plain text part is discovered"""
    out = {"body": None, "attachments": {}}
    # Based on https://stackoverflow.com/questions/25832631/download-attachments-from-gmail-using-gmail-api
    parts = [message]
    # breakpoint()
    while parts:
        cur = parts.pop()
        if "multipart" in cur["mimeType"]:
            parts.extend(cur["parts"])
        if cur["body"].get("attachmentId"):
            data = cur["body"].get(
                "data",  # May need API request to retrieve data
                (
                    gmail_service.users()
                    .messages()
                    .attachments()
                    .get(
                        userId="me",
                        messageId=message_id,
                        id=cur["body"]["attachmentId"],
                    )
                    .execute()["data"]
                ),
            )
            if data:
                data = base64.urlsafe_b64decode(data.encode("UTF-8"))
                # Key attachment data to names
                out["attachments"][cur["filename"]] = data
        # Beware: attachments can be text/plain
        elif cur["mimeType"] == "text/plain" and cur["body"].get(
            "data"
        ):  # vs text/html?
            out["body"] = decode_message(cur["body"]["data"], constants.html_decoder)

    return out


def extract_header(header, to_extract=None):
    """Extracts metadata fields from a message object"""
    if to_extract is None:
        to_extract = {
            "Delivered-To": "recipient",
            "From": "sender",
            "Subject": "subject",
            "Date": "date",
            "Message-ID": "id",
        }
    filtered = dict(zip(to_extract.values(), [None] * len(to_extract)))
    filtered = {
        **filtered,
        **{
            to_extract[component["name"]]: component["value"]
            for component in header
            if "name" in component.keys() and component["name"] in to_extract.keys()
        },
    }
    if filtered["id"] is None:
        filtered[
            "id"
        ] = f"Unidentified (sent {filtered.get('date', 'Unidentified (date unknown)')!r})"
    return filtered


# Largely taken from https://stackoverflow.com/questions/50630130/how-to-retrieve-the-whole-message-body-using-gmail-api-python
def decode_message(message, html_decoder=None):
    """
    Decodes an email message into plain HTML, optionally parsing HTML as well if an HTML2Text object is passed.

    :param message: An :code: `email.message` object
    :type message: email.message
    :param html_decoder: :code`HTML2Text` object with the desired configuration, used to parse the message HTML. Defaults to :code:`None`.
    :type html_decoder: HTML2Text
    :type parse_html: [TODO:type], optional
    """
    message = str(
        email.message_from_bytes(base64.urlsafe_b64decode(message.encode("ASCII")))
    )
    if html_decoder is not None:
        message = html_decoder.handle(message)
    return message


def format_print_dict(
    di,
    subvalue_extract=lambda x: " ".join(x)
    if isinstance(x, list) and len(x) > 0
    else format_print_dict(x),
    none_placeholder="None",
    *args,
):
    """
    Given a dict, returns a formatted sting suitable for printing its key-value pairs. A function to
    process dictionary entries, and placeholders for keys or values that are :code:`None`,
    may be specified.

    :param di: A dictionary.
    :type di: dict
    :param subvalue_extract: A function of one argument that processes each dict value, defaults to :code`lambda x: x` (the identity function).
    :type subvalue_extract: function, optional
    :param none_placeholder: String to print for keys and values that are :code:`None`, defaults to "None".
    :type none_placeholder: str, optional
    """
    if type(di) is not dict:
        return di
    if not di:
        return "Nothing to display"
    lpad = max([len(k) for k in di.keys()]) + 1
    fmt = "{:<" + str(lpad) + "}" + " {:" + str(lpad) + "}"
    return "\n".join(
        [
            fmt.format(
                (k if k is not None else none_placeholder) + ":",
                subvalue_extract(v)
                if subvalue_extract(v) not in (None, [], {})
                else none_placeholder,
            )
            for k, v in di.items()
        ]
    )


def print_sep(char="_", length=80):
    """Prints a line of underscores followed by newlines"""
    print((char * length) + "\n\n")


def page_response(gmail_service, max_emails=500, *args, **kwargs):
    """
    Parses a response to a query for emails, iterating over each page in the
    response object and flattening the result as a list.

    :param gmail_service: Gmail API client object
    :type gmail_service: googleapiclient.discovery.Resource
    :param max_emails: Maximum number of emails to return, defaults to 500 (the maximum number a single response can contain).
    :type max_emails: int, optional
    """

    response = {"nextPageToken": ""}
    messages = []

    while "nextPageToken" in response.keys():
        pageToken = response["nextPageToken"]
        response = get_message(gmail_service, *args, pageToken=pageToken, **kwargs)
        try:
            messages.extend(
                response["messages"][
                    : min(len(response["messages"]), max_emails - len(messages))
                ]
            )
        except:
            break

    return messages


# Largely copied from API quickstart
def create_message(sender, to, subject, message_text=""):
    """
    Creates an email message object from text, specifying sender, recipient, and subject.

    :param sender: Email address of the sender.
    :type sender: str
    :param to: Email address of the recipient.
    :type to: str
    :param subject: Subject of the email.
    :type subject: str
    :param message_text: Text of the email message body. Defaults to the ''.
    :type message_text: str
    """
    message = email.message_from_string(message_text)
    message = prepare_message(message, sender, to, subject)
    return package_message(message)


def package_message(message):
    """Encodes message and places it in object suitable for API request"""
    # The hero we needed: https://learndataanalysis.org/how-to-use-gmail-api-to-send-an-email-in-python/
    return {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}


def prepare_message(message, sender, to, subject):
    """Fills in "to", "from", and "subject" fields of an :code:`email.message` object"""
    if type(to) is list:
        to = "; ".join(to)
    message["to"] = to
    message["from"] = sender
    message["subject"] = subject
    return message


def create_message_with_attachment(sender, to, subject, message_text, attachments=None):
    """
    Creates an email message with a given body text, sender, and recipient, and
    attaches files specified in a list of paths.
    Largely copied from `this source <https://stackoverflow.com/questions/37201250/sending-email-via-gmail-python/43379469#43379469>`_.

    :param sender: Email address of the sender.
    :type sender: str
    :param to: Email address of the recipient.
    :type to: str
    :param subject: Subject of the email.
    :type subject: str
    :param message_text: Text of the email message body. Defaults to ''.
    :type message_text: str
    :param attachments: List of zero or more paths to files to attach, defaults to None
    :type attachments: List[str] , optional
    """
    message = MIMEMultipart()
    message = prepare_message(message, sender, to, subject)
    message.attach(MIMEText(message_text, "plain"))

    # Largely copied from https://stackoverflow.com/questions/37201250/sending-email-via-gmail-python/43379469#43379469
    for file in attachments or []:
        content_type, encoding = mimetypes.guess_type(file)
        if content_type is None or encoding is not None:
            content_type = "application/octet-stream"
        main_type, sub_type = content_type.split("/", 1)
        # Read file into MIME attachment and attach to message, skipping if file does not exist.
        try:
            with open(file, "rb") as f:
                attachment = MIMEBase(main_type, sub_type)
                attachment.set_payload(f.read())
                attachment.add_header(
                    "Content-Disposition", "attachment", filename=os.path.basename(file)
                )
                encoders.encode_base64(attachment)
                message.attach(attachment)
        except FileNotFoundError:
            pass
    return package_message(message)


def send_message(service, message, user_id="me"):
    """
    Sends an email message for a given user. Returns an HTTPError if sending fails.
    Largely copied from quickstart guide.

    :param service: Google API client object.
    :type service: googleapiclient.discovery.Resource
    :param message: email.message object representing the email to be sent.
    :type message: email.message
    :param user_id: Gmail user ID of the sender. Defaults to "me" (the id of the person for whom the API service is authorized).
    :type user_id: str, optional
    """
    try:
        message = (
            service.users().messages().send(userId=user_id, body=message).execute()
        )
        print(f"Message Id:{message['id']}")
    except HTTPError as error:
        print(f"HTTP error: {error}")
    return message


def normalize_path(path):
    """Expand ~ and all environment variables"""
    return os.path.expanduser(os.path.expandvars(path))


def path_exists(path):
    return os.path.exists(os.path.abspath(path))


def path_writeable(path, allow_overwrite=True):
    """Given a directory, determines whether the user has write permission. Given a file, determines whether
    they have write permission in the containing directory and
    optionally checks if the file already exists"""
    if os.path.isdir(path):
        out = os.access(path, os.W_OK)
    else:
        out = os.access(os.path.dirname(path), os.W_OK) and (
            allow_overwrite or not path_exists(path)
        )
    return out


def reduce_keys(di, keys):
    """Retrieve a value in a nested dictionary by indexing a list of keys in order"""
    return reduce(lambda di, key: di[key], keys, di)


def parse_emails(gmail_service, search_args, sub_args):
    """Conduct a search for emails using given parameters,
    collects the results, and execute associated subcommand"""
    max_emails = search_args.pop("max_emails")
    # Choose between OR or AND for search terms
    combinator = " OR " if (search_args.pop("or")) else " "
    # output = search_args.pop("output")
    # download_dir = search_args.pop("download_dir")
    search_args = {k: v for k, v in search_args.items() if v is not None}
    if search_args == {}:
        exit("No arguments provided")

    # request = ("{" * OR) + " ".join(search_args.values()) + ("}" * OR)
    request = combinator.join(search_args.values())

    messages = page_response(
        gmail_service, max_emails=max_emails, userId="me", q=request
    )

    if len(messages) == 0:
        print(f"No messages matched query {request!r}")
        exit()

    # Extract each payload, yielding MessagePart object
    raw_messages = [
        gmail_service.users()
        .messages()
        .get(userId="me", id=message["id"])
        .execute()["payload"]
        for message in messages
    ]
    gen = parse_message(gmail_service, raw_messages)
    parsed_messages = {mess["id"]: classes.ParsedMessage(**mess) for mess in gen}
    actions = {
        "print_emails": lambda: print_messages(
            parsed_messages, search_args, sub_args["await"]
        ),
        "store_emails": lambda: store_messages(
            parsed_messages,
            sub_args["output"],
            validate=True,
            verbose=sub_args["verbose"],
        ),
        "download_attachments": lambda: download_attachments(
            parsed_messages,
            sub_args["download_dir"],
            verbose=sub_args["verbose"],
            force=sub_args["force"],
        ),
    }
    # Call appropriate subcommand function
    action = actions.get(
        sub_args["subcommand"],
        lambda *args: exit(f"Unknown subcommand {sub_args['subcommand']!r}"),
    )
    action()


def print_messages(messages, search_args, await_=False):
    """Prints all recovered emails in order"""
    print(f"{len(messages)} email(s) retrieved")
    for message in messages.values():
        print(message)
        print_sep()
    if await_:
        menu = classes.OptionsMenu(
            header="Select option for retrieved emails:",
            options={
                "Download attachments": lambda: download_attachments(
                    messages, input("Directory: "), validate=True, verbose=True
                ),
                "Store emails": lambda: store_messages(
                    messages, input("Storage file: "), validate=True, verbose=True
                ),
                "Refine search": lambda: new_search(
                    messages, search_args, mode="additional"
                ),
                "New search": lambda: new_search(messages, search_args, mode="new"),
                "Quit": lambda: exit(0),
            },
        )
        # Add message ids to query
        while True:
            if choice := menu[menu.show_prompt()][1]:
                try:
                    choice()
                    choice = None  # Reset
                except SystemExit:
                    exit()
                except BaseException as e:
                    print(f"Error: {e}")


def download_attachments(
    messages, download_dir, validate=False, verbose=False, force=False
):
    """Downloads attachments in returned emails to a specialized directory,
    overwriting existing files only if specified"""
    download_dir = normalize_path(download_dir)
    if validate and not path_writeable(download_dir):
        raise classes.InvalidPathError(download_dir)

    downloaded = []
    for message in messages.values():
        for k, v in message.attachments.items():
            path = os.path.join(download_dir, k)
            # Only overwrite existing files if instructed
            if force or not path_exists(path):
                with open(path, "wb") as f:
                    f.write(v)
                    downloaded.append(k)
    if verbose:
        if len(downloaded) > 0:
            print("Downloaded:\n" + "\n".join(downloaded) + "\ninto " + download_dir)
        else:
            print("No attachments downloaded")


def store_messages(messages, output, validate=False, verbose=False):
    """Save returned email messages to a specified path"""
    filename = normalize_path(output.name if type(output) is TextIOWrapper else output)

    if validate and not path_writeable(filename, allow_overwrite=True):
        raise classes.InvalidPathError(filename)
    messages = {k: v.data for k, v in messages.items()}
    with open(filename, "w") as f:
        json.dump(messages, f)
    if verbose:
        print(f"Saved {len(messages)} email(s) to {filename}")


def new_search(messages, search_args, mode):
    """Prompt user for a new search. The mode argument controls
    whether to append to an existing search or start a new one"""
    if mode not in ("new", "additional"):
        raise ValueError(f"Mode must be 'new' or 'additional', not {mode!r}")
    ids = " ".join([k for k in messages.keys()])
    prompt = f"Enter {mode} search terms: "
    while True:
        try:
            while (new_args := input(prompt).split(" "))[0][0] != "-" and new_args[
                0
            ] != "print_emails":
                print("Flags must be used in search")
            # breakpoint()
            if mode == "additional":
                insert_args(new_args, "--ids", ids)
            else:
                search_args = None
            if not new_args[0] == "print_emails":
                new_args.insert(0, "print_emails")
            if not new_args[1] == "--await":
                new_args.insert(1, "--await")
            command.query_emails(new_args=new_args, prev_args=search_args)
        except Exception as e:
            print(f"Error parsing search: {e}")


def insert_args(args, extra_flag, extra_arg):
    """Inserts new arguments in arguments list in place"""
    try:
        which = args.index(extra_flag)
        args[which + 1] += " " + extra_arg
    except ValueError:
        args.extend([extra_flag, extra_arg])
