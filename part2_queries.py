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

# NB: the assignment sheet gives the position as (longitude, latitude),
# while haversine() expects (latitude, longitude).
PORTO_CITY_HALL_LONGITUDE = -8.62911
PORTO_CITY_HALL_LATITUDE = 41.15794


class QueryProgram:

    def __init__(self):
        self.connection = DbConnector()
        self.db_connection = self.connection.db_connection
        self.cursor = self.connection.cursor

    def print_query(self, query, params=None):
        """Run a SELECT, print the result as a table and return the rows."""
        self.cursor.execute(query, params)
        rows = self.cursor.fetchall()
        print(tabulate(rows, headers=self.cursor.column_names))
        return rows

    def task_1(self):
        """
        How many taxis, trips, and total GPS points are there?

        The counts are of the cleaned data: rows with a duplicated TRIP_ID were removed
        during the import, so the trip count is lower than the number of CSV rows.
        """
        raise NotImplementedError

    def task_2(self):
        """
        What is the average number of trips per taxi?
        """
        raise NotImplementedError

    def task_3(self):
        """
        List the top 20 taxis with the most trips.
        """
        raise NotImplementedError

    def task_4a(self):
        """
        What is the most used call type per taxi?

        To decide: what to show when a taxi has two call types with the same number of trips.
        """
        raise NotImplementedError

    def task_4b(self):
        """
        For each call type, compute the average trip duration and distance, and also report
        the share of trips starting in four time bands: 00-06, 06-12, 12-18, and 18-24.

        Duration is end_time - start_time. Distance is not stored, so it has to be computed
        from consecutive rows in gps_point (shared with task 5, see README "Open decisions").
        To decide: whether trips with fewer than 2 points (no duration, no distance) count
        in the averages, and whether the time bands use UTC (as stored) or Porto local time.
        """
        raise NotImplementedError

    def task_5(self):
        """
        Find the taxis with the most total hours driven as well as total distance driven.
        List them in order of total hours.

        Uses the same per-trip distance as task 4b. GPS outliers inflate the distance.
        """
        raise NotImplementedError

    def task_6(self):
        """
        Find the trips that passed within 100 m of Porto City Hall.
        (longitude, latitude) = (-8.62911, 41.15794)

        A trip passes within 100 m if at least one of its rows in gps_point does.
        """
        raise NotImplementedError

    def task_7(self):
        """
        Identify the number of invalid trips. An invalid trip is defined as a trip with
        fewer than 3 GPS points.

        These trips were deliberately kept by the import. trip.point_count holds the count.
        """
        raise NotImplementedError

    def task_8(self):
        """
        Find the trips that started on one calendar day and ended on the next (midnight crossers).

        To decide: whether midnight is in UTC (as stored) or in Porto local time.
        """
        raise NotImplementedError

    def task_9(self):
        """
        Find the trips whose start and end points are within 50 m of each other (circular trips).

        The start point has seq = 0 and the end point has seq = point_count - 1.
        To decide: whether trips with a single point (start = end) or invalid trips count.
        """
        raise NotImplementedError

    def task_10(self):
        """
        For each taxi, compute the average idle time between consecutive trips. List the
        top 20 taxis with the highest average idle time.

        Idle time is the next trip's start_time minus this trip's end_time for the same taxi.
        To decide: how to treat overlapping trips (negative idle time).
        """
        raise NotImplementedError


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
