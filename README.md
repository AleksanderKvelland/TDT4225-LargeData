# TDT4225 Assignment 2 - Porto taxi trajectories in MySQL

Group assignment for three students. We run MySQL 8.0.39 locally in Docker because the group has no course VM, so each of us has our own database and imports the data once.

**Deadline: 9 October 2026 at 14:00.**

## Status

| Part | File | State |
|---|---|---|
| Docker, credentials, connector | `docker-compose.yml`, `.env.example`, `DbConnector.py` | Done |
| Part 1.1: EDA | `part1_eda.ipynb` | Loading the data works. The nine analysis sections are empty. |
| Part 1.2: schema and import | `part1_import.py` | Works. Checked against the CSV for the first 20,000 rows. The full import has not been run yet. |
| Part 2: queries | `part2_queries.py` | All eleven queries (tasks 1-10, with 4a and 4b) are stubs. |
| Part 3: report | | Not started |

## Setup

You need Docker Desktop, Python 3 (tested with 3.14 on Windows) and the dataset from Blackboard.

1. Put the dataset at `porto/porto.csv`. The folder is git-ignored because the file is 1.9 GB.
2. Create your local settings: `cp .env.example .env`. The defaults work as they are.
3. Start MySQL: `docker compose up -d --wait`
4. Create a virtual environment and install the packages:

   ```
   python -m venv .venv
   .venv\Scripts\Activate.ps1        # Windows PowerShell
   source .venv/bin/activate         # macOS and Linux
   pip install -r requirements.txt
   ```

5. Check the connection: `python example.py`. It creates, prints and drops a small `Person` table.
6. Import the data:

   ```
   python part1_import.py --limit 20000    # first 20,000 rows, about 15 seconds
   python part1_import.py --reset          # the whole dataset, replacing what is there
   ```

   The full import is estimated at about 25 minutes and roughly 8 GB of Docker disk. Both figures are extrapolated from the 20,000-row sample, not measured.

Run the queries with `python part2_queries.py`, or only some of them with `python part2_queries.py 4a 6`. Open `part1_eda.ipynb` in VS Code or with `jupyter notebook` and select the `.venv` interpreter.

## Schema

The `CREATE TABLE` statements are in `TABLES` at the top of `part1_import.py`.

```
taxi        taxi_id (PK)
 └─ trip        trip_id (PK), taxi_id (FK), call_type, origin_call, origin_stand,
     │          start_time, end_time, day_type, missing_data, point_count
     └─ gps_point   trip_id (FK) + seq (PK), longitude, latitude
```

- **One row per GPS point.** The nested `POLYLINE` becomes 83.4 million rows in `gps_point`, so questions about individual points can be answered in SQL.
- **`seq` instead of a timestamp per point.** `seq` is the position in the polyline, starting at 0. Points are 15 seconds apart, so a point's time is `start_time + seq * 15 s`.
- **Two derived columns on `trip`.** `point_count` and `end_time` (`start_time + (point_count - 1) * 15 s`) are computed during the import. They repeat what `gps_point` already says, so that durations and point counts do not require aggregating 83 million rows.
- **Times are UTC.** `TIMESTAMP` is converted to a UTC `DATETIME`, and the server runs in UTC.
- **Foreign keys cascade.** Deleting a taxi deletes its trips, and deleting a trip deletes its points.
- **No tables for clients and taxi stands.** We only know their ids, which are stored on the trip.

## Cleaning rules

The import flags problems and keeps the rows, with one exception: duplicated trip ids. The counts are from a first scan of the CSV, before duplicates are removed. The EDA should reproduce them and confirm or change each rule.

| Issue | Rows affected | What the import does |
|---|---|---|
| Same `TRIP_ID` on several rows | 80 ids, 81 surplus rows | Keeps the row with the most GPS points. For 78 of the ids the rows differ, usually a stub with 0-2 points and one real trip. |
| Empty `ORIGIN_CALL` or `ORIGIN_STAND` | Every row has at least one of them empty | Stored as `NULL`. |
| Call type B without `ORIGIN_STAND` | 11,302 | Kept, with `origin_stand` `NULL`. |
| `MISSING_DATA` is true | 10 | Kept and flagged in `trip.missing_data`. |
| Empty `POLYLINE` | 5,901 | Kept with `point_count` 0 and no rows in `gps_point`. |
| Fewer than 3 GPS points | 43,904, including the empty ones | Kept, because task 7 asks us to count them. |
| `DAY_TYPE` is `A` on every row | 1,710,670 | Kept as it is. |
| GPS points far from Porto | Not counted yet | Kept as they are. See open decisions. |

## Suggested work packages

| Package | Contents |
|---|---|
| A: data quality | The EDA notebook, confirming the cleaning rules and schema, tasks 1, 2, 3 and 7, and Part 1 of the report. |
| B: taxi statistics | Tasks 4a, 4b, 5 and 10. |
| C: trajectories | Tasks 6, 8 and 9, and putting the report together. |

## Open decisions

These affect more than one task, so we should agree on them before writing the queries.

1. **Time zone.** Times are stored in UTC, and Porto is on UTC+1 in summer. The time bands in task 4b and the midnight crossers in task 8 give different answers in local time.
2. **Trip distance.** Tasks 4b and 5 both need the distance of each trip, which is not stored. We can compute it in the queries, or add a column to `trip` that the import fills using `haversine`. A new column means everyone imports again.
3. **GPS outliers.** Some points are hundreds of kilometres from Porto. They inflate distances (tasks 4b and 5) unless we filter them.
4. **Invalid trips in averages.** Trips with fewer than 3 points have little or no duration and distance. Decide whether they count in tasks 4b, 5, 9 and 10.

## Working together

- Work on one branch per package and merge with pull requests.
- If you change `TABLES` or a cleaning rule in `part1_import.py`, tell the group: everyone has to run `python part1_import.py --reset` again.
- Only one person should edit the notebook at a time, since notebooks merge badly.
- `.env` and the dataset are git-ignored and must stay out of the repository.
- The report must describe our use of AI. This baseline (Docker setup, connector changes, import script, query stubs, notebook skeleton and this README) was written with Claude Code. Note any further use as you go.

## Useful commands

```
docker compose up -d --wait                                  # start MySQL
docker compose stop                                          # stop it, keep the data
docker compose down -v                                       # delete the container and all imported data
docker exec -it tdt4225-mysql mysql -u porto_user -p porto   # MySQL shell
```

MySQL reads the user, password and database name from `.env` only the first time the container starts. To change them later, run `docker compose down -v` and start again.
