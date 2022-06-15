# Gmailtools

Gmailtools implements a command-line interface to the [Gmail API](https://developers.google.com/gmail/api). It includes utility functions to automate tasks like marking emails read or applying filters, as well as a more complex program to query, parse, and optionally store your emails using Gmail's search syntax.

## Authentication

To use the application, you'll need to obtain API credentials and store them
in a form understandable to the software. You can do this by creating a
project on the [Google Cloud Console](https://console.cloud.google.com/getting-started). Then, generate an OAuth 2.0 client ID and copy the information into a `.json` file.
Further instructions on how to do this can be found [here](https://developers.google.com/identity/protocols/oauth2/). By default, the function `authenticate`, which Gmailtools calls when one of its programs is run, looks for credentials from the environment variable `CREDENTIALS_PATH`, then looks for `credentials.json` in the home directory. You can also pass a file path to the `credentials_path` argument of `authenticate`. On first running the application, you will be prompted to authorize it. `authenticate` can also be configured to save an access token to skip this step in the future.

## Installation

If you have `pip` installed, you can install the current version of the software by running
```
python3 -m pip install --user --index-url https://test.pypi.org/simple/ --upgrade --no-deps Gmailtools
```
Enjoy!
