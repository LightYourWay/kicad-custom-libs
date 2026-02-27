# Our KiCad Library

## Setup

- Put `"token": "your-partdb-token"` in `symbol/Part-DB.kicad_httplib` in the `source` object just after the `root_url` field.
- Run `git update-index --assume-unchanged symbol/Part-DB.kicad_httplib` to prevent the token from being accidentally committed.
