"""
Part 1.2 - create the tables and import the cleaned Porto taxi dataset into MySQL.

    python part1_import.py                  import the whole dataset (takes a while)
    python part1_import.py --limit 20000    import only the first 20 000 CSV rows
    python part1_import.py --reset          drop the existing tables first

The schema is defined in TABLES. The cleaning rules are marked with "Cleaning rule"
comments below, and README.md explains the reasoning behind them.
"""
import argparse
import csv
import json
import os
import time
from datetime import datetime, timedelta, timezone
from itertools import islice

from haversine import haversine, Unit
from tabulate import tabulate

from DbConnector import DbConnector

CSV_PATH = os.path.join("porto", "porto.csv")
SAMPLE_INTERVAL_SECONDS = 15  # time between two consecutive GPS points in a POLYLINE
TRIPS_PER_BATCH = 1000        # trips (with all their GPS points) inserted per commit
PROGRESS_EVERY = 50_000       # print progress after this many CSV rows

# The tables are created in this order and dropped in the reverse order (foreign keys).
TABLES = {
    "taxi": """
        CREATE TABLE IF NOT EXISTS taxi (
            taxi_id INT UNSIGNED NOT NULL,
            PRIMARY KEY (taxi_id)
        )""",
    "trip": """
        CREATE TABLE IF NOT EXISTS trip (
            trip_id      BIGINT UNSIGNED     NOT NULL,
            taxi_id      INT UNSIGNED        NOT NULL,
            call_type    ENUM('A', 'B', 'C') NOT NULL,
            origin_call  INT UNSIGNED        NULL,      -- client id, only for call_type A
            origin_stand TINYINT UNSIGNED    NULL,      -- taxi stand id, only for call_type B
            start_time   DATETIME            NOT NULL,  -- TIMESTAMP converted to UTC
            end_time     DATETIME            NOT NULL,  -- derived: start_time + (point_count - 1) * 15 s
            day_type     ENUM('A', 'B', 'C') NOT NULL,
            missing_data BOOLEAN             NOT NULL,
            point_count  SMALLINT UNSIGNED   NOT NULL,  -- derived: number of rows in gps_point
            distance_km  DOUBLE              NOT NULL,  -- derived: distance between consecutive GPS points
            PRIMARY KEY (trip_id),
            INDEX idx_trip_taxi_start (taxi_id, start_time),
            FOREIGN KEY (taxi_id) REFERENCES taxi (taxi_id) ON DELETE CASCADE
        )""",
    "gps_point": """
        CREATE TABLE IF NOT EXISTS gps_point (
            trip_id   BIGINT UNSIGNED   NOT NULL,
            seq       SMALLINT UNSIGNED NOT NULL,  -- position in the POLYLINE, 0 = start of the trip
            longitude DOUBLE            NOT NULL,
            latitude  DOUBLE            NOT NULL,
            PRIMARY KEY (trip_id, seq),
            FOREIGN KEY (trip_id) REFERENCES trip (trip_id) ON DELETE CASCADE
        )""",
}

INSERT_TAXI = "INSERT INTO taxi (taxi_id) VALUES (%s)"
INSERT_TRIP = """INSERT INTO trip (trip_id, taxi_id, call_type, origin_call, origin_stand,
                                   start_time, end_time, day_type, missing_data, point_count, distance_km)
                 VALUES (%(trip_id)s, %(taxi_id)s, %(call_type)s, %(origin_call)s, %(origin_stand)s,
                         %(start_time)s, %(end_time)s, %(day_type)s, %(missing_data)s, %(point_count)s, %(distance_km)s)"""
INSERT_POINT = "INSERT INTO gps_point (trip_id, seq, longitude, latitude) VALUES (%s, %s, %s, %s)"


def read_csv(csv_path, limit=None):
    """Yield the rows of the dataset as dictionaries keyed by the CSV column names."""
    with open(csv_path, newline="", encoding="utf-8") as file:
        yield from islice(csv.DictReader(file), limit)


def int_or_none(value):
    """ORIGIN_CALL and ORIGIN_STAND are empty strings in the CSV when they are not set."""
    return int(value) if value else None

def calculate_polyline_distance_km(polyline):
    """Calculate the sum of haversine distances between consecutive GPS points in the polyline."""
    if len(polyline) < 2:
        return 0.0

    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(polyline, polyline[1:]):
        total += haversine((lat1, lon1), (lat2, lon2), unit=Unit.KILOMETERS)

    return total

def clean_trip(row):
    """Convert one raw CSV row to a trip (dict) and its GPS points (list of tuples)."""
    trip_id = int(row["TRIP_ID"])
    polyline = json.loads(row["POLYLINE"])  # [[longitude, latitude], ...], "[]" when empty

    # TIMESTAMP is Unix time. We store it as a UTC DATETIME, independent of the machine's time zone.
    start_time = datetime.fromtimestamp(int(row["TIMESTAMP"]), tz=timezone.utc).replace(tzinfo=None)
    # A trip with n points lasts (n - 1) * 15 seconds. Trips with 0 or 1 points get no duration.
    duration = timedelta(seconds=SAMPLE_INTERVAL_SECONDS * max(len(polyline) - 1, 0))

    trip = {
        "trip_id": trip_id,
        "taxi_id": int(row["TAXI_ID"]),
        "call_type": row["CALL_TYPE"],
        # Cleaning rule 2: empty ORIGIN_CALL / ORIGIN_STAND become NULL
        "origin_call": int_or_none(row["ORIGIN_CALL"]),
        "origin_stand": int_or_none(row["ORIGIN_STAND"]),
        "start_time": start_time,
        "end_time": start_time + duration,
        "day_type": row["DAY_TYPE"],
        # Cleaning rule 3: trips with missing GPS points are kept and flagged, not removed
        "missing_data": row["MISSING_DATA"] == "True",
        # Cleaning rule 4: trips with few or no GPS points are kept (Part 2 task 7 counts them)
        "point_count": len(polyline),
        "distance_km": calculate_polyline_distance_km(polyline),
    }
    points = [(trip_id, seq, longitude, latitude) for seq, (longitude, latitude) in enumerate(polyline)]
    return trip, points


def scan_csv(csv_path, limit=None):
    """
    First pass over the CSV, needed before anything can be inserted. Returns
    - the ids of all taxis, so the taxi table is filled before the trips that reference it
    - the highest GPS point count per TRIP_ID, used to pick one row for each duplicated id
    - the number of rows read
    """
    taxi_ids = set()
    most_points = {}
    row_count = 0
    for row in read_csv(csv_path, limit):
        row_count += 1
        taxi_ids.add(int(row["TAXI_ID"]))
        trip_id = int(row["TRIP_ID"])
        point_count = len(json.loads(row["POLYLINE"]))
        if point_count > most_points.get(trip_id, -1):
            most_points[trip_id] = point_count
    return taxi_ids, most_points, row_count


class ImportProgram:

    def __init__(self):
        self.connection = DbConnector()
        self.db_connection = self.connection.db_connection
        self.cursor = self.connection.cursor

    def create_tables(self):
        for query in TABLES.values():
            self.cursor.execute(query)
        self.db_connection.commit()

    def drop_tables(self):
        for table_name in reversed(TABLES):
            print("Dropping table %s..." % table_name)
            self.cursor.execute("DROP TABLE IF EXISTS %s" % table_name)

    def count_rows(self, table_name):
        self.cursor.execute("SELECT COUNT(*) FROM %s" % table_name)
        return self.cursor.fetchone()[0]

    def insert_batch(self, trips, points):
        """Insert a batch of trips and all their GPS points in one transaction."""
        if trips:
            self.cursor.executemany(INSERT_TRIP, trips)
        if points:
            self.cursor.executemany(INSERT_POINT, points)
        self.db_connection.commit()

    def insert_data(self, csv_path, limit=None):
        started = time.time()

        print("Pass 1 of 2: scanning %s for taxis and duplicated trip ids..." % csv_path)
        taxi_ids, most_points, row_count = scan_csv(csv_path, limit)
        self.cursor.executemany(INSERT_TAXI, [(taxi_id,) for taxi_id in sorted(taxi_ids)])
        self.db_connection.commit()
        print("Found %d rows and %d taxis after %.0f s" % (row_count, len(taxi_ids), time.time() - started))

        print("Pass 2 of 2: inserting trips and GPS points...")
        stats = {
            "CSV rows read": 0,
            "Rows skipped (duplicated TRIP_ID)": 0,
            "Trips inserted": 0,
            "GPS points inserted": 0,
            "Trips with MISSING_DATA = True": 0,
            "Trips without GPS points": 0,
            "Trips with fewer than 3 GPS points": 0,
            "Call type B trips without ORIGIN_STAND": 0,
        }
        trips, points = [], []
        for row in read_csv(csv_path, limit):
            stats["CSV rows read"] += 1
            trip, trip_points = clean_trip(row)

            # Cleaning rule 1: TRIP_ID should be unique, but some ids appear on several different
            # rows. We keep the row with the most GPS points (the first one if there is a tie).
            if most_points.get(trip["trip_id"]) != trip["point_count"]:
                stats["Rows skipped (duplicated TRIP_ID)"] += 1
                continue
            del most_points[trip["trip_id"]]  # any later row with this id is now a duplicate

            trips.append(trip)
            points.extend(trip_points)
            stats["Trips inserted"] += 1
            stats["GPS points inserted"] += trip["point_count"]
            stats["Trips with MISSING_DATA = True"] += trip["missing_data"]
            stats["Trips without GPS points"] += trip["point_count"] == 0
            stats["Trips with fewer than 3 GPS points"] += trip["point_count"] < 3
            stats["Call type B trips without ORIGIN_STAND"] += (
                trip["call_type"] == "B" and trip["origin_stand"] is None)

            if len(trips) >= TRIPS_PER_BATCH:
                self.insert_batch(trips, points)
                trips, points = [], []

            if stats["CSV rows read"] % PROGRESS_EVERY == 0:
                print("  %d of %d rows (%.0f %%) after %.0f s" % (
                    stats["CSV rows read"], row_count,
                    100 * stats["CSV rows read"] / row_count, time.time() - started))
        self.insert_batch(trips, points)

        print("\nImport finished in %.0f s" % (time.time() - started))
        print(tabulate(stats.items(), headers=["Import summary", "Count"], intfmt=","))

    def show_row_counts(self):
        rows = [(table_name, self.count_rows(table_name)) for table_name in TABLES]
        print("\n" + tabulate(rows, headers=["Table", "Rows in database"], intfmt=","))


def main():
    parser = argparse.ArgumentParser(description="Create the tables and import the Porto taxi dataset.")
    parser.add_argument("--csv", default=CSV_PATH, help="path to porto.csv (default: %(default)s)")
    parser.add_argument("--limit", type=int, default=None, help="only import the first LIMIT rows of the CSV")
    parser.add_argument("--reset", action="store_true", help="drop the existing tables before importing")
    args = parser.parse_args()

    program = None
    try:
        program = ImportProgram()
        if args.reset:
            program.drop_tables()
        program.create_tables()
        # The taxi table is filled first, so it is empty only if nothing has been imported
        if program.count_rows("taxi") > 0:
            print("The tables already contain data. Run with --reset to drop them and import again.")
            return
        program.insert_data(args.csv, args.limit)
        program.show_row_counts()
    finally:
        if program:
            program.connection.close_connection()


if __name__ == '__main__':
    main()
