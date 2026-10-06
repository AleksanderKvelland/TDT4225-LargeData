"""
Part 2 - queries answering the questions in the assignment sheet.

    python part2_queries.py          run every task
    python part2_queries.py 4a 6     run only tasks 4a and 6

Each task is one method on QueryProgram. The docstring starts with the question from the
assignment sheet (printed above the result), followed by notes on what has to be decided.
The tables are described in part1_import.py (TABLES) and in README.md.
"""
import inspect
import sys

from tabulate import tabulate

from DbConnector import DbConnector

TASKS = ["1", "2", "3", "4a", "4b", "5", "6", "7", "8", "9", "10"]
PREVIEW_ROW_COUNT = 10

class QueryProgram:

    def __init__(self):
        self.connection = DbConnector()
        self.db_connection = self.connection.db_connection
        self.cursor = self.connection.cursor

    def print_query(self, query, params=None):
        """Run a SELECT, print the first rows as a table and return every row."""
        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()
        preview_rows = rows[:PREVIEW_ROW_COUNT]
        print(tabulate(preview_rows, headers=self.cursor.column_names))
        if len(rows) > PREVIEW_ROW_COUNT:
            print("(%d rows, showing the first %d)" % (len(rows), PREVIEW_ROW_COUNT))
        return rows

    def task_1(self):
        """
        How many taxis, trips, and total GPS points are there?
        """
        
        query = """
        SELECT 
            (SELECT COUNT(*) FROM taxi) AS taxi_count,
            (SELECT COUNT(*) FROM trip) AS trip_count,
            (SELECT COUNT(*) FROM gps_point) AS gps_point_count;
        """
        self.print_query(query)

    def task_2(self):
        """
        What is the average number of trips per taxi?
        """

        query = """
        SELECT 
            AVG(trip_count) AS avg_trips_per_taxi 
        FROM (
            SELECT COUNT(*) AS trip_count FROM trip GROUP BY taxi_id
        ) AS trip_counts;
        """
        self.print_query(query)

    def task_3(self):
        """
        List the top 20 taxis with the most trips.
        """

        query = """
        SELECT 
            taxi_id, 
            COUNT(*) AS trip_count 
        FROM trip 
        GROUP BY taxi_id 
        ORDER BY trip_count DESC 
        LIMIT 20;
        """
        self.print_query(query)

    def task_4a(self):
        """
        What is the most used call type per taxi?
        """

        query = """
        SELECT taxi_id,
            call_type AS most_used_call_type
        FROM (
        SELECT taxi_id,
                call_type,
                COUNT(*) AS trip_count,
                ROW_NUMBER() OVER (
                    PARTITION BY taxi_id
                    ORDER BY COUNT(*) DESC, call_type
                ) AS rnk
        FROM trip
        GROUP BY taxi_id, call_type
        ) ranked
        WHERE rnk = 1
        ORDER BY taxi_id;
        """
        self.print_query(query)

    def task_4b(self):
        """
        For each call type, compute the average trip duration and distance, and also report
        the share of trips starting in four time bands: 00-06, 06-12, 12-18, and 18-24.
        """

        query = """
        SELECT call_type,
            AVG(TIMESTAMPDIFF(SECOND, start_time, end_time)) AS avg_trip_duration_seconds,
            AVG(distance_km) AS avg_trip_distance_km,
            AVG(CASE WHEN HOUR(start_time) < 6 THEN 1 ELSE 0 END) AS share_00_06,
            AVG(CASE WHEN HOUR(start_time) >= 6 AND HOUR(start_time) < 12 THEN 1 ELSE 0 END) AS share_06_12,
            AVG(CASE WHEN HOUR(start_time) >= 12 AND HOUR(start_time) < 18 THEN 1 ELSE 0 END) AS share_12_18,
            AVG(CASE WHEN HOUR(start_time) >= 18 THEN 1 ELSE 0 END) AS share_18_24
        FROM trip
        WHERE distance_km > 0
        GROUP BY call_type;
        """
        self.print_query(query)

    def task_5(self):
        """
        Find the taxis with the most total hours driven as well as total distance driven.
        List them in order of total hours.
        """

        query = """
        SELECT taxi_id,
            SUM(TIMESTAMPDIFF(SECOND, start_time, end_time)) / 3600.0 AS total_hours_driven,
            SUM(distance_km) AS total_distance_km
        FROM trip
        GROUP BY taxi_id
        ORDER BY total_hours_driven DESC;
        """
        self.print_query(query)

    def task_6(self):
        """
        Find the trips that passed within 100 m of Porto City Hall.
        (longitude, latitude) = (-8.62911, 41.15794)
        """

        query = """
        SELECT DISTINCT trip_id
        FROM gps_point
        WHERE ST_Distance_Sphere(
            POINT(longitude, latitude),
            POINT(-8.62911, 41.15794)
        ) <= 100;
        """
        self.print_query(query)

    def task_7(self):
        """
        Identify the number of invalid trips. An invalid trip is defined as a trip with
        fewer than 3 GPS points.
        """

        query = """
        SELECT COUNT(*) AS invalid_trip_count
        FROM trip
        WHERE point_count < 3;
        """
        self.print_query(query)

    def task_8(self):
        """
        Find the trips that started on one calendar day and ended on the next (midnight crossers).
        """

        query = """
        SELECT trip_id
        FROM trip
        WHERE TIMESTAMPDIFF(DAY, DATE(start_time), DATE(end_time)) = 1;
        """
        self.print_query(query)

    def task_9(self):
        """
        Find the trips whose start and end points are within 50 m of each other (circular trips).
        """

        query = """
        SELECT trip.trip_id
        FROM trip
        JOIN gps_point AS start_pt
            ON start_pt.trip_id = trip.trip_id AND start_pt.seq = 0
        JOIN gps_point AS end_pt
            ON end_pt.trip_id = trip.trip_id AND end_pt.seq = trip.point_count - 1
        WHERE trip.point_count >= 2
        AND ST_Distance_Sphere(
                POINT(start_pt.longitude, start_pt.latitude),
                POINT(end_pt.longitude, end_pt.latitude)
            ) <= 50;
        """
        self.print_query(query)

    def task_10(self):
        """
        For each taxi, compute the average idle time between consecutive trips. List the
        top 20 taxis with the highest average idle time.
        """

        query = """
        WITH ordered AS (
            SELECT
                taxi_id,
                start_time,
                end_time,
                LEAD(start_time) OVER (
                    PARTITION BY taxi_id
                    ORDER BY start_time, trip_id
                ) AS next_start
            FROM trip
        ),
        idle AS (
            SELECT
                taxi_id,
                TIMESTAMPDIFF(SECOND, end_time, next_start) / 3600.0 AS idle_hours
            FROM ordered
            WHERE next_start IS NOT NULL
            AND TIMESTAMPDIFF(SECOND, end_time, next_start) >= 0
        )
        SELECT
            taxi_id,
            AVG(idle_hours) AS avg_idle_hours
        FROM idle
        GROUP BY taxi_id
        ORDER BY avg_idle_hours DESC
        LIMIT 20;
        """
        self.print_query(query)


def main():
    tasks = sys.argv[1:] or TASKS
    unknown = [task for task in tasks if task not in TASKS]
    if unknown:
        sys.exit("Unknown task(s): %s. Choose from: %s" % (", ".join(unknown), " ".join(TASKS)))

    program = None
    try:
        program = QueryProgram()
        for task in tasks:
            method = getattr(program, "task_" + task)
            # The first paragraph of the docstring is the question from the assignment sheet
            question = inspect.getdoc(method).split("\n\n")[0]
            print("\nTask %s: %s\n" % (task, question))
            try:
                method()
            except NotImplementedError:
                print("Not implemented yet")
    finally:
        if program:
            program.connection.close_connection()


if __name__ == '__main__':
    main()
