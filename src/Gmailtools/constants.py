import html2text


html_decoder = html2text.HTML2Text()
# html_decoder.ignore_links = True
html_decoder.ignore_images = True
html_decoder.body_width = 80

# Default list of GMail auth scopes - better to use just one
SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
]
