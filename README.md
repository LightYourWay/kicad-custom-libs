# Our KiCad Library

## Setup

`symbol/Part-DB.kicad_httplib` holds a personal Part-DB API token, so it is not
tracked by git. Generate it from the template after cloning:

```sh
./scripts/init-partdb-lib.py
```

The script prompts for the Part-DB URL and the API token (token input is
hidden). Only the base URL of the instance is needed — the KiCad API sub path is
appended automatically, and the library description is derived from the host
name. The scheme may be omitted: `https` is assumed for named hosts, `http` for
bare IP addresses. The script also accepts `--url <base-url>` / `--token <token>`, the
`PARTDB_URL` / `PARTDB_TOKEN` environment variables, and `--force` to regenerate
the file after a token rotation.

Before writing the file, the script runs the same endpoint validation KiCad
runs and aborts if the API does not answer or the token is rejected. Use
`--skip-check` to write the file anyway, and `--timeout <seconds>` to adjust the
probe timeout.

Get a token from Part-DB under User Settings -> API tokens.

Requires Python 3.8 or newer. On Windows run it as
`python scripts\init-partdb-lib.py`; KiCad ships a suitable interpreter if none
is installed system-wide.
