import sqlite3
import pandas as pd

df = pd.read_csv("data/ola_cleaned.csv")
df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

with sqlite3.connect("data/ola.db") as con:
    df.to_sql("ola_rides", con, if_exists="replace", index=False)
    print(con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT Booking_ID) FROM ola_rides"
    ).fetchone())