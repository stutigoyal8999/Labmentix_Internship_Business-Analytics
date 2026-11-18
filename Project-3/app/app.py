"""
Ola Ride Insights - Streamlit app
=================================
Pages
  1. Overview            - KPI cards + charts (all filterable from the sidebar)
  2. SQL Query Explorer  - the 10 project queries, run live on SQLite, with search + CSV download
  3. Data Explorer       - filterable / searchable table of the full ola_rides data
  4. Power BI Dashboard  - dashboard screenshots (+ optional live Power BI embed)

Run from the Project-3 folder:
    python -m streamlit run app/app.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent          # Project-3/
DB_PATH = BASE_DIR / "data" / "ola.db"
SHOT_DIR = BASE_DIR / "powerbi" / "screenshots"

# Paste your Power BI "Publish to web" / embed URL here if you ever publish it.
# Leave empty to show only the screenshots.
POWERBI_EMBED_URL = ""

# (tab title, screenshot file name, caption)
DASHBOARD_PAGES = [
    ("Overall", "overall.png", "Booking status split, KPIs and trends"),
    ("Vehicle Type", "vehicle_type.png", "Performance by vehicle type"),
    ("Revenue", "revenue.png", "Revenue by payment method and day"),
    ("Cancellation", "cancellation.png", "Customer and driver cancellation reasons"),
    ("Ratings", "ratings.png", "Customer and driver rating analysis"),
]

OLA_GREEN = "#1C7C54"
OLA_YELLOW = "#F5C518"

st.set_page_config(page_title="Ola Ride Insights", page_icon="🚖", layout="wide")

st.markdown(
    f"""
    <style>
      [data-testid="stSidebar"] {{ background-color: #111418; }}
      [data-testid="stSidebar"] * {{ color: #f1f1f1; }}
      h1, h2, h3 {{ color: {OLA_GREEN}; }}
      div[data-testid="stMetric"] {{
          background: #ffffff; border-left: 6px solid {OLA_YELLOW};
          padding: 12px 16px; border-radius: 8px;
          box-shadow: 0 1px 4px rgba(0,0,0,.12);
      }}
      div[data-testid="stMetric"] * {{ color: #111418 !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# The 10 required SQL queries
# --------------------------------------------------------------------------
QUERIES = {
    "Q1. Retrieve all successful bookings": """
SELECT *
FROM ola_rides
WHERE Booking_Status = 'Success';""",
    "Q2. Average ride distance for each vehicle type": """
SELECT Vehicle_Type,
       ROUND(AVG(Ride_Distance), 2) AS avg_ride_distance
FROM ola_rides
WHERE Booking_Status = 'Success'
GROUP BY Vehicle_Type
ORDER BY avg_ride_distance DESC;""",
    "Q3. Total number of rides cancelled by customers": """
SELECT COUNT(*) AS cancelled_by_customer
FROM ola_rides
WHERE Booking_Status = 'Canceled by Customer';""",
    "Q4. Top 5 customers with the highest number of rides": """
SELECT Customer_ID,
       COUNT(*) AS total_rides
FROM ola_rides
GROUP BY Customer_ID
ORDER BY total_rides DESC, Customer_ID
LIMIT 5;""",
    "Q5. Rides cancelled by drivers for personal & car related issues": """
SELECT COUNT(*) AS driver_cancel_personal_car_issues
FROM ola_rides
WHERE Canceled_Rides_by_Driver = 'Personal & Car related issue';""",
    "Q6. Max and min driver ratings for Prime Sedan": """
SELECT MAX(Driver_Ratings) AS max_driver_rating,
       MIN(Driver_Ratings) AS min_driver_rating
FROM ola_rides
WHERE Vehicle_Type = 'Prime Sedan'
  AND Driver_Ratings IS NOT NULL;""",
    "Q7. Rides paid via UPI": """
SELECT *
FROM ola_rides
WHERE Payment_Method = 'UPI';""",
    "Q8. Average customer rating per vehicle type": """
SELECT Vehicle_Type,
       ROUND(AVG(Customer_Rating), 2) AS avg_customer_rating
FROM ola_rides
GROUP BY Vehicle_Type
ORDER BY avg_customer_rating DESC;""",
    "Q9. Total booking value of successful rides": """
SELECT SUM(Booking_Value) AS total_booking_value
FROM ola_rides
WHERE Booking_Status = 'Success';""",
    "Q10. Incomplete rides along with the reason": """
SELECT Booking_ID, Date, Vehicle_Type, Pickup_Location,
       Drop_Location, Incomplete_Rides_Reason
FROM ola_rides
WHERE Incomplete_Rides = 'Yes';""",
}


# --------------------------------------------------------------------------
# Data access
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Run a read-only SQL query against the SQLite database."""
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        return pd.read_sql_query(sql, con, params=params)


def get_filter_options():
    vehicles = run_query("SELECT DISTINCT Vehicle_Type FROM ola_rides ORDER BY 1")["Vehicle_Type"].tolist()
    statuses = run_query("SELECT DISTINCT Booking_Status FROM ola_rides ORDER BY 1")["Booking_Status"].tolist()
    payments = run_query("SELECT DISTINCT Payment_Method FROM ola_rides ORDER BY 1")["Payment_Method"].tolist()
    dates = run_query("SELECT MIN(Date) AS d0, MAX(Date) AS d1 FROM ola_rides").iloc[0]
    return vehicles, statuses, payments, pd.to_datetime(dates["d0"]).date(), pd.to_datetime(dates["d1"]).date()


def build_where(vehicles, statuses, payments, d0, d1):
    """Build a parameterised WHERE clause from the sidebar filters."""
    clauses, params = ["Date BETWEEN ? AND ?"], [str(d0), str(d1)]
    for col, vals in (("Vehicle_Type", vehicles), ("Booking_Status", statuses), ("Payment_Method", payments)):
        if vals:
            clauses.append(f"{col} IN ({','.join('?' * len(vals))})")
            params += list(vals)
    return " WHERE " + " AND ".join(clauses), tuple(params)


# --------------------------------------------------------------------------
# Guard: database must exist
# --------------------------------------------------------------------------
if not DB_PATH.exists():
    st.error(f"Database not found at `{DB_PATH}`. Run `python sql/load_db.py` from the Project-3 folder first.")
    st.stop()

# --------------------------------------------------------------------------
# Sidebar: navigation + global filters
# --------------------------------------------------------------------------
st.sidebar.title("🚖 Ola Ride Insights")
page = st.sidebar.radio(
    "Navigate",
    ["Overview", "SQL Query Explorer", "Data Explorer", "Power BI Dashboard"],
)

all_vehicles, all_statuses, all_payments, min_d, max_d = get_filter_options()

st.sidebar.markdown("---")
st.sidebar.subheader("Filters")
st.sidebar.caption("Apply to Overview and Data Explorer")
f_dates = st.sidebar.date_input("Date range", (min_d, max_d), min_value=min_d, max_value=max_d)
f_vehicles = st.sidebar.multiselect("Vehicle type", all_vehicles)
f_statuses = st.sidebar.multiselect("Booking status", all_statuses)
f_payments = st.sidebar.multiselect("Payment method", all_payments)

# date_input returns a 1-tuple while the user is still picking the end date
d_start, d_end = (f_dates if isinstance(f_dates, tuple) and len(f_dates) == 2 else (min_d, max_d))
WHERE, PARAMS = build_where(f_vehicles, f_statuses, f_payments, d_start, d_end)

st.sidebar.markdown("---")
st.sidebar.caption("Data: Ola ride bookings, July 2024 · SQLite + Power BI + Streamlit")

# --------------------------------------------------------------------------
# Page 1: Overview
# --------------------------------------------------------------------------
if page == "Overview":
    st.title("Ola Ride Insights")
    st.caption("Interactive overview of bookings, revenue, cancellations and ratings. Use the sidebar filters.")

    kpi = run_query(
        f"""SELECT COUNT(*) AS total,
                   SUM(Booking_Status='Success') AS success,
                   SUM(CASE WHEN Booking_Status='Success' THEN Booking_Value END) AS revenue,
                   AVG(CASE WHEN Booking_Status='Success' THEN Ride_Distance END) AS avg_dist,
                   AVG(Customer_Rating) AS cust_rating,
                   AVG(Driver_Ratings) AS drv_rating
            FROM ola_rides{WHERE}""",
        PARAMS,
    ).iloc[0]

    if not kpi["total"]:
        st.warning("No rides match the current filters.")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total bookings", f"{int(kpi['total']):,}")
    c2.metric("Success rate", f"{(kpi['success'] or 0) / kpi['total']:.1%}")
    c3.metric("Revenue (successful)", f"₹{(kpi['revenue'] or 0):,.0f}")
    c4.metric("Avg distance (km)", f"{(kpi['avg_dist'] or 0):.1f}")
    c5, c6, _, _ = st.columns(4)
    c5.metric("Avg customer rating", f"{(kpi['cust_rating'] or 0):.2f}")
    c6.metric("Avg driver rating", f"{(kpi['drv_rating'] or 0):.2f}")

    st.markdown("---")
    left, right = st.columns(2)

    with left:
        st.subheader("Booking status")
        d = run_query(f"SELECT Booking_Status, COUNT(*) AS rides FROM ola_rides{WHERE} GROUP BY 1 ORDER BY 2 DESC", PARAMS)
        st.bar_chart(d.set_index("Booking_Status"), color=OLA_GREEN)

    with right:
        st.subheader("Rides by vehicle type")
        d = run_query(f"SELECT Vehicle_Type, COUNT(*) AS rides FROM ola_rides{WHERE} GROUP BY 1 ORDER BY 2 DESC", PARAMS)
        st.bar_chart(d.set_index("Vehicle_Type"), color=OLA_YELLOW)

    left, right = st.columns(2)
    with left:
        st.subheader("Revenue by payment method (successful rides)")
        d = run_query(
            f"""SELECT Payment_Method, SUM(Booking_Value) AS revenue FROM ola_rides
                {WHERE} AND Booking_Status='Success' GROUP BY 1 ORDER BY 2 DESC""",
            PARAMS,
        )
        st.bar_chart(d.set_index("Payment_Method"), color=OLA_GREEN)

    with right:
        st.subheader("Rides by time of day")
        d = run_query(f"SELECT Time_Bucket, COUNT(*) AS rides FROM ola_rides{WHERE} GROUP BY 1", PARAMS)
        order = ["Night", "Morning", "Afternoon", "Evening", "Late Night"]
        d["Time_Bucket"] = pd.Categorical(d["Time_Bucket"], categories=order, ordered=True)
        st.bar_chart(d.sort_values("Time_Bucket").set_index("Time_Bucket"), color=OLA_YELLOW)

    st.subheader("Daily bookings trend")
    d = run_query(f"SELECT Date, COUNT(*) AS bookings FROM ola_rides{WHERE} GROUP BY 1 ORDER BY 1", PARAMS)
    st.line_chart(d.set_index("Date"), color=OLA_GREEN)

    left, right = st.columns(2)
    with left:
        st.subheader("Customer cancellation reasons")
        d = run_query(
            f"""SELECT Canceled_Rides_by_Customer AS reason, COUNT(*) AS rides FROM ola_rides
                {WHERE} AND Canceled_Rides_by_Customer <> 'Not Applicable' GROUP BY 1 ORDER BY 2 DESC""",
            PARAMS,
        )
        if d.empty:
            st.info("No customer cancellations in this selection.")
        else:
            st.bar_chart(d.set_index("reason"), horizontal=True, color=OLA_YELLOW)
    with right:
        st.subheader("Driver cancellation reasons")
        d = run_query(
            f"""SELECT Canceled_Rides_by_Driver AS reason, COUNT(*) AS rides FROM ola_rides
                {WHERE} AND Canceled_Rides_by_Driver <> 'Not Applicable' GROUP BY 1 ORDER BY 2 DESC""",
            PARAMS,
        )
        if d.empty:
            st.info("No driver cancellations in this selection.")
        else:
            st.bar_chart(d.set_index("reason"), horizontal=True, color=OLA_GREEN)

# --------------------------------------------------------------------------
# Page 2: SQL Query Explorer
# --------------------------------------------------------------------------
elif page == "SQL Query Explorer":
    st.title("SQL Query Explorer")
    st.caption("The 10 project queries run live against the SQLite database (`data/ola.db`).")

    choice = st.selectbox("Choose a query", list(QUERIES))
    sql = QUERIES[choice].strip()
    st.code(sql, language="sql")

    df = run_query(sql)
    st.success(f"{len(df):,} row(s) returned")

    # Search box: filters the result rows (any column) after the query has run
    term = st.text_input("🔎 Search within results", placeholder="Type any text, e.g. Prime Sedan, CID954071, Vehicle Breakdown")
    if term:
        mask = df.astype(str).apply(lambda col: col.str.contains(term, case=False, na=False)).any(axis=1)
        df = df[mask]
        st.caption(f"{len(df):,} row(s) match '{term}'")

    # Single-value results look better as a metric
    if df.shape == (1, 1):
        val = df.iloc[0, 0]
        st.metric(df.columns[0].replace("_", " ").title(), f"{val:,.0f}" if isinstance(val, (int, float)) else val)
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.download_button("⬇ Download result as CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name=f"{choice.split('.')[0].lower()}_result.csv", mime="text/csv")

    with st.expander("Run your own SQL (read-only)"):
        custom = st.text_area("SQL", "SELECT Vehicle_Type, COUNT(*) AS rides FROM ola_rides GROUP BY Vehicle_Type;")
        if st.button("Run"):
            if not custom.strip().lower().startswith("select"):
                st.error("Only SELECT statements are allowed.")
            else:
                try:
                    st.dataframe(run_query(custom), use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Query failed: {e}")

# --------------------------------------------------------------------------
# Page 3: Data Explorer
# --------------------------------------------------------------------------
elif page == "Data Explorer":
    st.title("Data Explorer")
    st.caption("Browse the full dataset. Sidebar filters apply here too.")

    search = st.text_input("🔎 Search (Booking ID, Customer ID, pickup or drop location)")
    sql = f"SELECT * FROM ola_rides{WHERE}"
    params = list(PARAMS)
    if search:
        sql += " AND (Booking_ID LIKE ? OR Customer_ID LIKE ? OR Pickup_Location LIKE ? OR Drop_Location LIKE ?)"
        params += [f"%{search}%"] * 4
    df = run_query(sql + " LIMIT 5000", tuple(params))

    total = run_query(sql.replace("SELECT *", "SELECT COUNT(*) AS n"), tuple(params)).iloc[0, 0]
    st.write(f"**{int(total):,}** matching rides" + (" (showing first 5,000)" if total > 5000 else ""))
    st.dataframe(df.drop(columns=["Vehicle_Images"], errors="ignore"), use_container_width=True, hide_index=True)
    st.download_button("⬇ Download shown rows as CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="ola_rides_filtered.csv", mime="text/csv")

# --------------------------------------------------------------------------
# Page 4: Power BI Dashboard
# --------------------------------------------------------------------------
else:
    st.title("Power BI Dashboard")
    st.caption("Five-page interactive dashboard built in Power BI Desktop (`powerbi/ola_dashboard.pbix`).")

    if POWERBI_EMBED_URL:
        st.subheader("Live dashboard")
        st.components.v1.iframe(POWERBI_EMBED_URL, height=620, scrolling=False)
        st.markdown("---")

    tabs = st.tabs([t[0] for t in DASHBOARD_PAGES])
    for tab, (title, fname, caption) in zip(tabs, DASHBOARD_PAGES):
        with tab:
            img = SHOT_DIR / fname
            if img.exists():
                st.image(str(img), caption=caption, use_container_width=True)
            else:
                st.info(f"Screenshot `{fname}` not found in `powerbi/screenshots/`.")