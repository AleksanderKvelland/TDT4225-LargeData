import os
from pathlib import Path

import mysql.connector as mysql
from dotenv import load_dotenv

# Load the connection settings from the .env file next to this file (see .env.example).
# The same .env file configures the MySQL container in docker-compose.yml.
load_dotenv(Path(__file__).with_name(".env"))


class DbConnector:
    """
    Connects to the MySQL server running in the Docker container (see docker-compose.yml).
    Connector needs HOST, DATABASE, USER and PASSWORD to connect,
    while PORT is optional and should be 3306.

    The values are read from environment variables, so no password ends up in git:
    DB_HOST = "127.0.0.1" // The container publishes MySQL on this machine only
    DB_NAME = "porto" // Database name, created by the container on first start
    DB_USER = "testuser" // User created by the container on first start
    DB_PASSWORD = "..." // The password set for said user in .env
    DB_PORT = "3306" // Optional
    """

    def __init__(self,
                 HOST=os.getenv("DB_HOST", "127.0.0.1"),
                 DATABASE=os.getenv("DB_NAME", "porto"),
                 USER=os.getenv("DB_USER", "testuser"),
                 PASSWORD=os.getenv("DB_PASSWORD"),
                 PORT=int(os.getenv("DB_PORT", "3306"))):
        # Connect to the database
        try:
            self.db_connection = mysql.connect(host=HOST, database=DATABASE, user=USER, password=PASSWORD, port=PORT)
        except Exception as e:
            print("ERROR: Failed to connect to db:", e)
            print("Is the container running (docker compose up -d --wait) and does .env exist?")
            raise

        # Get the db cursor
        self.cursor = self.db_connection.cursor()

        print("Connected to:", self.db_connection.get_server_info())
        # get database information
        self.cursor.execute("select database();")
        database_name = self.cursor.fetchone()
        print("You are connected to the database:", database_name)
        print("-----------------------------------------------\n")

    def close_connection(self):
        # the server info is no longer available once the connection is closed
        server_info = self.db_connection.get_server_info()
        # close the cursor
        self.cursor.close()
        # close the DB connection
        self.db_connection.close()
        print("\n-----------------------------------------------")
        print("Connection to %s is closed" % server_info)
