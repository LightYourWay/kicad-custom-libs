# Our KiCad Library

Symbols, footprints and 3D models we use for our own boards: displays,
connectors, logic, LEDs, sensors, and more.

## Setup 🔧

Nothing in here uses absolute or relative paths. Every file the library refers
to goes through the `LRV_CUSTOM_LIBS` variable, so you can clone the repo
wherever you want.

Clone it, then go to **Preferences → Configure Paths** in KiCad and add
`LRV_CUSTOM_LIBS` pointing to your clone. This is the part that is set per
machine.

Add the libraries themselves per project, in the **Project Specific Libraries**
tab of each dialog:

- **Preferences → Manage Symbol Libraries**:
  `${LRV_CUSTOM_LIBS}/symbol/LRV.kicad_sym`
- **Preferences → Manage Footprint Libraries**:
  `${LRV_CUSTOM_LIBS}/footprints/LRV`

Because both entries use the variable, the resulting `sym-lib-table` and
`fp-lib-table` stay machine independent. Commit them with the project, and
everyone else only needs `LRV_CUSTOM_LIBS` set on their own machine.

Everything is build using KiCad 10. Older versions may still work, but we can't
guarantee it.

## Use with Part-DB 📦

We manage our components in [Part-DB](https://github.com/Part-DB/Part-DB-server)
and use KiCad's HTTP library to place parts straight from it. This is convenient but optional, the library also works without it.

The config file is not in the repo, since it usually carries an API token. If
you run your own instance, you can generate it with:

```sh
./scripts/init-partdb-lib.py
```

The script asks for the Part-DB URL and an API token (**User Settings → API
tokens**), tests the connection and writes `symbol/Part-DB.kicad_httplib`. That
file is gitignored. 🔑

If your instance allows anonymous access, leave the token prompt empty, or pass
`--no-token`.

Entering `parts.example.com` is enough, the API path is added automatically.

Add the result in **Manage Symbol Libraries** as
`${LRV_CUSTOM_LIBS}/symbol/Part-DB.kicad_httplib`.

### Options

- `--force` overwrites an existing config file
- `--url` and `--token` skip the prompts, as do `PARTDB_URL` and `PARTDB_TOKEN`
- `--no-token` configures anonymous access
- `--skip-check` writes the file without testing the connection
- `--help` lists everything

Requires Python 3.8 or later. On Windows: `python scripts\init-partdb-lib.py`.
