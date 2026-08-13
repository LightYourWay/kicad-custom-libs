#!/usr/bin/env python3
"""Initialise the local Part-DB HTTP library file from its template.

symbol/Part-DB.kicad_httplib carries a personal Part-DB API token, so it is
git-ignored and has to be generated locally. Run this after a fresh clone and
whenever the token is rotated.
"""

import argparse
import getpass
import ipaddress
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOST_PLACEHOLDER = "__PARTDB_HOST__"
URL_PLACEHOLDER = "__PARTDB_ROOT_URL__"
TOKEN_PLACEHOLDER = "__PARTDB_TOKEN__"

# Part-DB always exposes its KiCad API under the same sub path, so only the
# instance base URL has to be supplied.
API_SUB_PATH = "en/kicad-api/"

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "symbol" / "Part-DB.kicad_httplib.template"
TARGET = REPO_ROOT / "symbol" / "Part-DB.kicad_httplib"


def fail(message: str) -> NoReturn:
    # Keep the preceding progress lines ahead of the error when stdout is piped.
    sys.stdout.flush()
    print(f"❌ {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate symbol/Part-DB.kicad_httplib from its template. Only the "
            "base URL of the Part-DB instance is needed -- the KiCad API sub "
            "path is appended automatically, and the library description is "
            "derived from the host name. The scheme may be omitted; https is "
            "assumed for named hosts and http for bare IP addresses."
        ),
        epilog=(
            "Get a token from Part-DB under User Settings -> API tokens. "
            "Instances that allow anonymous access do not need one."
        ),
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("PARTDB_URL", ""),
        help="base URL of the Part-DB instance, e.g. parts.example.com "
        "(default: $PARTDB_URL, otherwise prompted)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("PARTDB_TOKEN", ""),
        help="API token to inject (default: $PARTDB_TOKEN, otherwise prompted "
        "with hidden input)",
    )
    parser.add_argument(
        "--no-token",
        action="store_true",
        help="configure anonymous access, for instances that allow it",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing library file",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="write the file without probing the API first",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        metavar="SECONDS",
        help="timeout for the API check (default: %(default)s)",
    )
    return parser.parse_args()


def prompt_missing(args: argparse.Namespace) -> tuple:
    """Return URL and token; an empty token means anonymous access."""
    url, token = args.url.strip(), args.token.strip()
    interactive = sys.stdin.isatty()

    if token and args.no_token:
        fail("--token and --no-token contradict each other")

    if not url:
        if not interactive:
            fail("no URL given and stdin is not a terminal; use --url or $PARTDB_URL")
        while not url:
            url = input("🔗 Part-DB URL (e.g. parts.example.com): ").strip()

    if not token and not args.no_token:
        if not interactive:
            fail(
                "no token given and stdin is not a terminal; use --token, "
                "$PARTDB_TOKEN, or --no-token for anonymous access"
            )
        token = getpass.getpass(
            "🔑 Part-DB API token (leave empty for anonymous access): "
        ).strip()

    return url, token


def add_default_scheme(url: str) -> str:
    """Assume a scheme when none was typed.

    Named hosts get https, bare IP addresses get http -- those are usually
    local instances without a certificate.
    """
    # Not urlsplit(): it reads "parts.example.com:8080" as a scheme plus path.
    if "://" in url:
        return url

    hostname = urlsplit(f"//{url}").hostname or ""

    try:
        ipaddress.ip_address(hostname)
        scheme = "http"
    except ValueError:
        scheme = "https"

    return f"{scheme}://{url}"


def resolve_urls(url: str) -> tuple:
    """Return the host name for the description and the full KiCad API URL."""
    url = add_default_scheme(url)
    split = urlsplit(url)

    if split.scheme not in ("http", "https"):
        fail("URL must start with http:// or https://")

    # netloc keeps the port, which a bare hostname would drop; userinfo is not
    # part of the host name.
    host = split.netloc.rsplit("@", 1)[-1]
    if not host:
        fail(f"cannot derive a host name from URL: {url}")

    base = url.rstrip("/")

    # Tolerate a full API URL being pasted instead of just the instance base URL.
    api_url = f"{base}/" if base.endswith("/kicad-api") else f"{base}/{API_SUB_PATH}"

    return host, api_url


class _NoRedirect(HTTPRedirectHandler):
    """Turn redirects into errors: Part-DB bounces unauthenticated requests to
    its login page, which would otherwise look like a successful response."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_json(url: str, token: str, timeout: float):
    # KiCad always sends this header, empty token or not, so send the same thing
    # -- otherwise the check could pass where KiCad later fails.
    request = Request(
        url,
        headers={"Accept": "application/json", "Authorization": f"Token {token}"},
    )

    try:
        with build_opener(_NoRedirect).open(request, timeout=timeout) as response:
            payload = response.read()
    except HTTPError as error:
        if error.code in (401, 403):
            if token:
                fail(f"API rejected the token (HTTP {error.code}) at {url}")
            fail(f"API needs a token (HTTP {error.code}) at {url}")
        if error.code in (301, 302, 303, 307, 308):
            if token:
                fail(f"API redirected to a login page at {url}; the token was not accepted")
            fail(f"API redirected to a login page at {url}; it needs a token")
        fail(f"API returned HTTP {error.code} at {url}")
    except URLError as error:
        fail(
            f"cannot reach {url}: {error.reason}\n"
            f"   💡 pass --skip-check to write the file anyway"
        )

    try:
        return json.loads(payload)
    except ValueError:
        fail(f"API did not return JSON at {url}; is this a Part-DB KiCad API URL?")


def check_api(api_url: str, api_version: str, token: str, timeout: float) -> None:
    """Run the same endpoint validation KiCad runs, and nothing beyond it.

    KiCad appends the API version to the root URL (sch_io_http_lib.cpp) and then
    fetches it, requiring a categories and a parts entry in the response
    (HTTP_LIB_CONNECTION::validateHttpLibraryEndpoints).
    """
    root = f"{api_url}{api_version}/"

    document = fetch_json(root, token, timeout)
    if not isinstance(document, dict):
        fail(f"unexpected API response at {root}; is this a Part-DB KiCad API URL?")

    # Presence, not truthiness -- Part-DB answers with empty strings here, which
    # KiCad accepts.
    missing = [key for key in ("categories", "parts") if key not in document]
    if missing:
        fail(
            f"API response at {root} has no {' and no '.join(missing)} entry; "
            f"is this the KiCad API of a Part-DB instance?"
        )


def render(template: str, host: str, api_url: str, token: str):
    """Substitute placeholders in every string value of the parsed template."""
    replacements = {
        HOST_PLACEHOLDER: host,
        URL_PLACEHOLDER: api_url,
        TOKEN_PLACEHOLDER: token,
    }

    def walk(node):
        if isinstance(node, dict):
            return {key: walk(value) for key, value in node.items()}
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, str):
            for placeholder, value in replacements.items():
                node = node.replace(placeholder, value)
        return node

    return walk(json.loads(template))


def write_private(path: Path, text: str) -> None:
    """Write the file so it is never briefly readable by others."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.chmod(path, 0o600)


def warn_if_tracked(path: Path) -> None:
    try:
        tracked = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", "--", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
    except FileNotFoundError:
        return

    if tracked:
        sys.stdout.flush()
        print(
            f"⚠️  {path} is still tracked by git, so the token can be "
            f"committed by accident.\n"
            f"   💡 untrack it with:\n"
            f'      git -C "{REPO_ROOT}" update-index --no-assume-unchanged -- "{path}"\n'
            f'      git -C "{REPO_ROOT}" rm --cached -- "{path}"',
            file=sys.stderr,
        )


def main() -> None:
    args = parse_args()

    if not TEMPLATE.is_file():
        fail(f"template not found: {TEMPLATE}")

    if TARGET.exists() and not args.force:
        fail(f"{TARGET} already exists; pass --force to overwrite it")

    url, token = prompt_missing(args)
    host, api_url = resolve_urls(url)

    template = TEMPLATE.read_text(encoding="utf-8")
    for placeholder in (HOST_PLACEHOLDER, URL_PLACEHOLDER, TOKEN_PLACEHOLDER):
        if placeholder not in template:
            fail(f"placeholder {placeholder} not found in {TEMPLATE}")

    try:
        api_version = json.loads(template)["source"]["api_version"]
    except (ValueError, KeyError, TypeError):
        fail(f"cannot read source.api_version from {TEMPLATE}")

    if args.skip_check:
        print(f"⏭️  skipping API check for {api_url}")
    else:
        print(f"🔍 checking {api_url}{api_version}/ ...")
        check_api(api_url, api_version, token, args.timeout)
        print("✅ API reachable" + (", token accepted" if token else ""))

    document = render(template, host, api_url, token)
    if not token:
        # KiCad defaults the token to an empty string, so leave the key out.
        document["source"].pop("token", None)

    write_private(TARGET, json.dumps(document, indent=2) + "\n")

    print(f"📝 wrote {TARGET} (mode 600)")
    print(f"   🔗 API URL: {api_url}")
    print(f"   🏠 host:    {host}")
    print(f"   🔑 auth:    {'token' if token else 'anonymous'}")

    warn_if_tracked(TARGET)


if __name__ == "__main__":
    main()
