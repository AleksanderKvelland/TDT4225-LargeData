# TDT4225 Assignment 2 - Porto taxi trajectories in MySQL

We run MySQL 8.0.39 locally in Docker because the group has no course VM, so each of us has our own database and imports the data once.

**Deadline: 9 October 2026 at 14:00.**

**Contributors:** Aleksander Kvelland, André Klarpås, Brage Andreas Hoven

## Setup

You need Docker Desktop, Python 3 (tested with 3.14 on Windows) and the dataset from Canvas.

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
     │          start_time, end_time, missing_data, point_count, distance_km
     └─ gps_point   trip_id (FK) + seq (PK), longitude, latitude
```

- **One row per GPS point.** The nested `POLYLINE` becomes 83.4 million rows in `gps_point`, so questions about individual points can be answered in SQL.
- **`seq` instead of a timestamp per point.** `seq` is the position in the polyline, starting at 0. Points are 15 seconds apart, so a point's time is `start_time + seq * 15 s`.
- **Three derived columns on `trip`.** `point_count`, `end_time` (`start_time + (point_count - 1) * 15 s`, or `start_time` itself for trips with no points) and `distance_km` (the sum of the haversine distances between consecutive points, 0 for trips with fewer than two points) are computed during the import. They repeat what `gps_point` already says, so that durations, distances and point counts do not require aggregating 83 million rows.
- **No column for `DAY_TYPE`.** It is `A` (normal day) on every row of the CSV, also on holidays, so the import leaves it out. See section 3.3 of `part1_eda.ipynb`.
- **Times are UTC.** `TIMESTAMP` is converted to a UTC `DATETIME`, and the server runs in UTC.
- **Foreign keys cascade.** Deleting a taxi deletes its trips, and deleting a trip deletes its points.
- **A table for taxis, but none for clients or taxi stands.** All three are known only by their id, so `taxi` has a single column and stores nothing that `trip.taxi_id` does not. We keep it because the taxi is the owner of a trip: every trip has exactly one, and tasks 1, 2, 3, 4a, 5 and 10 in Part 2 are asked per taxi. `origin_call` and `origin_stand` are optional details of a trip, set only for call type A and B respectively, and no task asks about them, so they stay as nullable columns on `trip`.

## Useful commands

```
docker compose up -d --wait                                  # start MySQL
docker compose stop                                          # stop it, keep the data
docker compose down -v                                       # delete the container and all imported data
docker exec -it tdt4225-mysql mysql -u testuser -p porto   # MySQL shell
```

MySQL reads the user, password and database name from `.env` only the first time the container starts. To change them later, run `docker compose down -v` and start again.
