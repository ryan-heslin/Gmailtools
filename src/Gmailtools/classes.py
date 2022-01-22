import argparse as ap

# from Gmailtools import utils
import utils
import sys
import os


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
        except RuntimeError:
            raise KeyError(var)

    def __repr__(self) -> str:
        return self.dict.__repr__()


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
        if not utils.validate_path(argument_values, lambda x: os.access(x, os.W_OK)):
            sys.exit(
                f"Directory {argument_values!r} is not a valid path, or you lack write permission"
            )
        setattr(namespace, "download_dir", argument_values)
