import argparse as ap

# from Gmailtools import utils
import utils
import sys
import os
from functools import lru_cache
from collections import ChainMap
from os.path import abspath


class TupleDict:

    # Merge dicts into one dict
    def __init__(self, *args, **kwargs):
        """
        This class represents a dict keyed by tuples. The tuples must be disjoint
        (i.e., no element can be present in multiple tuples). Lookups return the
        value keyed to the tuple containing the value looked up, :code:`KeyError` if
        none does. The dictionary is constructed from dictionaries passed via
        :code:`args` and key-value pairs passed via :code:`kwargs`.

        :raises ValueError: Raised if any element is present in multiple tuple keys.
        """

        di = {**{k: v for di in [*args] for k, v in di.items()}, **kwargs}
        if len({el for tup in di.keys() for el in tup}) < sum(
            len(tup) for tup in di.keys()
        ):
            raise ValueError("At least one value in multiple key tuples")
        self.dict = di

    def __getitem__(self, var, **kwargs):
        out = (v for k, v in self.dict.items() for subkey in k if var == subkey)
        try:
            return next(out)
        except StopIteration:
            raise KeyError(var)

    def __repr__(self) -> str:
        return self.dict.__repr__()


class PartialUpdateDict(dict):
    """Scalar values are updated as usual, but strings are appended instead"""

    def __init__(self, *args):
        super().__init__(*args)

    def update(self, di):
        for k, v in di.items():
            new = (
                v
                if type(self.get(k)) is not str or type(v) is not str
                else f"{self.__getitem__(k)} {v}"
            )
            self.__setitem__(k, new)


class ParsedMessage(dict):
    def __init__(
        self,
        id,
        date,
        sender=None,
        recipient=None,
        body=None,
        subject=None,
        attachments=None,
    ):
        self.id = id
        self.date = date
        self.sender = sender
        self.recipient = recipient
        self.body = body
        self.subject = subject
        self.attachments = {} if attachments is None else attachments

    @property
    def n_attachments(self):
        return len(self.attachments)

    @property
    def data(self):
        return {
            "From": self.sender,
            "To": self.recipient,
            "Subject": self.subject,
            "Date": self.date,
            "Body": self.body,
            "Attachments": self.n_attachments,
        }

    def __repr__(self):
        return utils.format_print_dict(self.data)


class QueryAction(ap.Action):

    mapping = TupleDict(
        {
            ("-f", "--from"): {"category": "from", "sep": ":", "surround": ""},
            ("-w", "--words"): {"category": "", "sep": "", "surround": '"'},
            ("-t", " --to"): {"category": "to", "sep": ":", "surround": ""},
            ("-l", " --label"): {"category": "label", "sep": ":", "surround": ""},
            ("-c", "--category"): {
                "category": "category",
                "sep": ":",
                "surround": "",
            },
            ("-s", " --subject"): {
                "category": "subject",
                "sep": ":",
                "surround": "",
            },
            ("--filename",): {"category": "filename", "sep": ":", "surround": ""},
            ("-b", "--before"): {"category": "before", "sep": ":", "surround": ""},
            ("-a", "--after"): {"category": "after", "sep": ":", "surround": ""},
            ("-i", "--ids"): {
                "category": "rfc822msgid",
                "sep": ":",
                "group_or": True,
                "joiner": " OR ",
            },
        }
    )

    """Overrides superclass method.
    Maps each option string to the corresponding search term, then
    prepends it to corresponding arguments separated by colons"""

    def __init__(self, option_strings, dest, nargs, **kwargs):
        super().__init__(option_strings, dest, nargs, **kwargs)

    def __call__(self, parser, namespace, argument_values, option_strings=None):
        # Date validation: confirm that a consistent separator is used by replacing all digit characters with nul byte and checking length
        if __class__.mapping[option_strings]["category"] in ("before", "after"):
            # From https://stackoverflow.com/questions/32538305/using-translate-on-a-string-to-strip-digits-python-3
            translation = str.maketrans("", "", "0123456789")
            sep = set(argument_values.translate(translation))
            if len(sep) > 2:
                print("Error: Used multiple separators in date string")
                sys.exit()
            sep = str(sep.pop())
            utils.validate_before_present(
                argument_values,
                ("%Y/%m/%d".replace("/", sep), "%m/%d/%Y".replace("/", sep)),
            )
        argument_values = utils.append_category(
            argument_values, **self.mapping[option_strings]
        )
        setattr(namespace, self.mapping[option_strings]["category"], argument_values)


class MaxAction(ap.Action):
    def __call__(self, parser, namespace, argument_values, option_strings=None):
        if argument_values is None:
            argument_values = 500
        elif argument_values < 1 or argument_values > 500 or argument_values % 1 != 0:
            sys.exit(
                f"Invalid max {argument_values}. Must be integer between 1 and 500 inclusive."
            )
        setattr(namespace, "max_emails", argument_values)


class DirAction(ap.Action):
    def __call__(self, parser, namespace, argument_values, option_strings=None):
        path = abspath(argument_values)
        if not utils.validate_path(path, lambda x: os.access(x, os.W_OK)):
            utils.path_err(argument_values)
        setattr(namespace, "download_dir", path)


class OptionsMenu:
    """Simple options menu linking numbered options to actions"""

    def __init__(self, header: str, options: dict, prompt="Enter option: "):
        self.header = header
        self.prompt = prompt
        self.options = [x for x in options.keys()]
        self.valid_range = [1, len(self.options)]
        self.actions = {int(i + 1): v for i, v in enumerate(options.values())}
        # Print padding
        self._pad = len(str(max(self.actions.keys()))) + 1

    def __repr__(self):
        return "\n".join(
            [self.header] + OptionsMenu.sequential_number(self.options, self._pad)
        )

    def __getitem__(self, num):
        try:
            num = int(num)
        except:
            print("Selection must be coercible to integer")
            return None, None
        # Return option and associated key - refactor this trash later
        try:
            # Return displayed menu item and corresponding action
            return (self.options[num - 1], self.actions[num])
        except KeyError:
            print("Invalid selection")
            return None, None

    @staticmethod
    def sequential_number(lst, lpad, offset=1) -> list:
        fmt = "{:<" + str(lpad) + "} {:>" + str(lpad) + "}"
        return [fmt.format(f"{i + offset}.", x) for i, x in enumerate(lst)]

    def show_prompt(self):
        print(self.__repr__() + "\n")
        response = input(self.prompt)
        return response


class InvalidPathError(Exception):
    def __init__(self, path):
        self.message = f"{path} does not exist, or you lack write permission for it"
        super().__init__(self.message)
