<!--
Step-by-step guide to loading the Inside the Game synthetic dataset into Microsoft Fabric and reporting on it.
It covers the lakehouse, the PySpark load notebook, the Direct Lake semantic model in TMDL, and a three-page report.
Everything in fabric/ is checked offline against the Python schemas by python -m insidegame.fabric.check.
-->

# Microsoft Fabric: lakehouse, semantic model, and report

The dataset generator writes five JSON Lines files. This guide turns them into six Delta tables in a Fabric
lakehouse, puts a Direct Lake semantic model with relationships and DAX measures on top, and builds a three-page
Power BI report. The artifacts live in [`fabric/`](../fabric):

| Path | What it is |
|---|---|
| `fabric/notebooks/load_lakehouse.ipynb` | PySpark notebook: explicit-schema load, derived columns, `clubs` dimension, Delta writes |
| `fabric/InsideTheGame.SemanticModel/` | Direct Lake semantic model in TMDL: 5 tables, 6 relationships, 10 measures |
| `backend/src/insidegame/fabric/schema.py` | Source of truth for every column, its type, and nullability |

Tables written by the notebook:

| Table | Grain | Notes |
|---|---|---|
| `matches` | one row per match | includes `home_team_id` and `away_team_id` |
| `clubs` | one row per club | built from `matches`: `team_id`, `club_name`, `style` |
| `events` | one row per event | adds `phase` (`00-15` to `75-90+`, 15-minute buckets); `moment_kinds` stored as JSON text |
| `players` | one row per player per match | per-match player statistics |
| `moments` | one row per key moment | adds `scout_pattern` for Tactical Scout flags; `facts`, `player_ids`, `event_ids` stored as JSON text |
| `tracking` | one row per sampled frame | lakehouse only (not in the semantic model); `players` stored as JSON text |

## Prerequisites

- A Microsoft Fabric capacity or a Fabric trial, and a workspace on it where you can create items.
- This repository checked out locally, with the backend environment from the main README (`.venv`).
- For route A of step 5: the workspace connected (or connectable) to a Git repository through Fabric Git
  integration, or Power BI Desktop with TMDL view.

## 1. Create a lakehouse

In the workspace choose **New item**, then **Lakehouse**, and name it `insidegame`. Either a schema-enabled or a
classic lakehouse works; tables land in the `dbo` schema of a schema-enabled lakehouse (see Troubleshooting).

## 2. Generate the data

Use the committed two-match sample in `data/sample/`, or generate a larger set from `backend/`:

```bash
cd backend
../.venv/bin/python -m insidegame.datasets.generate --matches 48 --start-seed 1 --out ../data/synthetic
```

Check it before uploading (step 7 explains the command):

```bash
../.venv/bin/python -m insidegame.fabric.check --data ../data/synthetic --fabric ../fabric
```

## 3. Upload the files

In the lakehouse explorer, open **Files**, create a folder `insidegame`, and upload `matches.jsonl`,
`events.jsonl`, `players.jsonl`, `moments.jsonl`, and `tracking.jsonl` into it. The dataset card (`README.md`) is
not needed. The notebook reads from `Files/insidegame/`; change `SOURCE_DIR` in its second cell for another folder.

## 4. Import and run the notebook

1. In the workspace choose **Import**, then **Notebook**, then **From this computer**, and pick
   `fabric/notebooks/load_lakehouse.ipynb`.
2. Open it, and in the lakehouse explorer pane choose **Add lakehouse** and attach `insidegame` as the default
   lakehouse.
3. **Run all**. The load cell reads each file with its explicit Spark schema in `FAILFAST` mode, so a file that does
   not match its schema stops the run with the offending record. The write cell overwrites the six Delta tables, and
   the last cell prints a row count per table.

For the committed sample the counts are: matches 2, clubs 3, events 4921, players 44, moments 33, tracking 985.

## 5. Create the semantic model

### Route A: deploy the TMDL folder

1. Open the lakehouse's **SQL analytics endpoint**, then **Settings**, then **SQL endpoint**, and copy the SQL
   connection string (for example `abcd1234.datawarehouse.fabric.microsoft.com`). The endpoint's item id is the
   GUID after `/lakewarehouses/` (or `/sqlendpoints/`) in the browser address bar while it is open.
2. In `fabric/InsideTheGame.SemanticModel/definition/expressions.tmdl` replace `<SQL_ENDPOINT>` with the connection
   string and `<LAKEHOUSE_SQL_ENDPOINT_ID>` with the item id.
3. Either connect the workspace to the repository with **Workspace settings**, **Git integration**, Git folder
   `fabric`, then **Source control** and **Update all**; or open Power BI Desktop, open **TMDL view**, paste the
   table, relationship, and expression scripts, apply them, and publish to the workspace.
4. In the semantic model's settings, set the cloud connection to the SQL endpoint with single sign-on (or a
   workspace identity) and refresh once to frame the Direct Lake tables.

### Route B (fallback): build the model in the browser

1. In the lakehouse choose **New semantic model**, name it `InsideTheGame`, and select `matches`, `clubs`,
   `events`, `players`, and `moments` (leave `tracking` out).
2. Open the model, choose **Manage relationships**, and add these many-to-one, single-direction relationships:

   | From (many) | To (one) |
   |---|---|
   | `events[match_id]` | `matches[match_id]` |
   | `players[match_id]` | `matches[match_id]` |
   | `moments[match_id]` | `matches[match_id]` |
   | `events[team_id]` | `clubs[team_id]` |
   | `players[team_id]` | `clubs[team_id]` |
   | `moments[team_id]` | `clubs[team_id]` |

3. Add the measures with **New measure** on the table named in the TMDL file, copying each expression and format
   string from `definition/tables/players.tmdl` (`Goals`, `Expected Goals`, `Goals minus xG`, `Shots`,
   `Pass Accuracy %`), `events.tmdl` (`Avg Pass Difficulty`, `xT Added`, `Avg Momentum`, `Pass Share %`), and
   `moments.tmdl` (`Scout Flags`).

## 6. Build the report

From the semantic model choose **Create new report** and build three pages. Add a slicer on `matches[match_id]`
(with `matches[home]` and `matches[away]` as tooltips) to every page.

**Page 1: Club xG vs goals.** A clustered bar chart with `clubs[club_name]` on the axis and `Goals` and
`Expected Goals` as values; a card with `Goals minus xG`; a table with `clubs[club_name]`, `Shots`,
`Pass Accuracy %`, and `xT Added`. Clubs that score above their xG are finishing well; below, they are wasteful
or unlucky.

**Page 2: Passing and pressure by phase.** A line chart with `events[phase]` on the axis and `Avg Momentum` as the
value; a clustered column chart with `events[phase]` on the axis, `clubs[club_name]` as the legend, and
`Pass Share %` as the value (a possession proxy: each club's share of the passes in that phase); a column chart of
`Avg Pass Difficulty` by `events[phase]`. Momentum is home-relative (-1 away on top, +1 home on top), so read it
for one selected match by phase, not per club.

**Page 3: Tactical Scout flags.** A card with `Scout Flags`; a bar chart with `moments[scout_pattern]` on the axis
and `Scout Flags` as the value; a table with `moments[minute_label]`, `clubs[club_name]`,
`moments[scout_pattern]`, `moments[importance]`, and `moments[facts]`, filtered to `moments[kind]` is
`tactical_pattern`. These are the flags the live Tactical Scout agent raised, for example a flank exposed
repeatedly before a goal.

## 7. Verify offline

Everything in `fabric/` is checked against the Python schemas without a Fabric account. From `backend/`:

```bash
../.venv/bin/python -m insidegame.fabric.check --data ../data/sample --fabric ../fabric
```

It validates every row of the five JSONL files (missing or unexpected columns, types, nulls), confirms each
notebook code cell parses, that the notebook's `SOURCE_SCHEMAS` equal the Python Spark DDL, and that all six tables
are written, and cross-checks the TMDL tables, column data types, relationships, and measure column references.
It prints `OK: 5 tables, ...` and exits 0, or one `<file>:<line>: <message>` line per problem (at most 50) and
exits 1. The defaults for `--data` and `--fabric` are `../data/sample` and `../fabric`, relative to `backend/`.
The same checks run in the backend test suite (`tests/test_fabric_schema.py`, `tests/test_fabric_model.py`).

## Troubleshooting

- **Tables not found by the semantic model:** on a schema-enabled lakehouse the notebook writes to `dbo`, which
  matches `schemaName: dbo` in the TMDL partitions. On a classic lakehouse the SQL endpoint also exposes the
  tables under `dbo`; if your endpoint uses another schema, change `schemaName` in each table file.
- **`FAILFAST` error in the load cell:** a record does not match its schema, usually because the files come from
  an older generator (before `home_team_id` and `away_team_id`). Regenerate, run step 7, and upload again.
- **`tracking.players` fails to load:** the schema reads each `[player_id, x, y]` entry as strings. If your Spark
  runtime refuses that coercion, change the `players` type in `SOURCE_SCHEMAS["tracking"]` to `STRING` and drop the
  `to_json` call for it (the offline check will flag the schema change until `schema.py` is updated to match).
- **Direct Lake falls back or cannot frame:** check the model's cloud connection credentials and that the
  placeholders in `expressions.tmdl` were replaced; refresh the model after each notebook run.
