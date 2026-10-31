"""
Real Estate Investment Advisor - Streamlit App
-----------------------------------------------
Run from the project folder:   streamlit run app.py
"""

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

st.set_page_config(page_title="Real Estate Investment Advisor", page_icon="🏠", layout="wide")

BASE_DIR = Path(__file__).parent  # folder containing app.py, so paths work wherever the app is started from
DATA_PATH = BASE_DIR / "data" / "cleaned_housing_data.csv"
REFERENCE_YEAR = 2025  # Age_of_Property in the data = 2025 - Year_Built
AMENITIES = ["Gym", "Pool", "Clubhouse", "Garden", "Playground"]
CATEGORICAL_FEATURES = [
    "City", "Property_Type", "Furnished_Status", "Public_Transport_Accessibility",
    "Parking_Space", "Security", "Facing", "Owner_Type", "Availability_Status",
]


# ---------------------------------------------------------------------------
# Loading (cached so it only happens once)
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    return pd.read_csv(DATA_PATH)


@st.cache_resource
def load_models():
    clf = joblib.load(BASE_DIR / "models" / "classifier.joblib")
    reg = joblib.load(BASE_DIR / "models" / "regressor.joblib")
    with open(BASE_DIR / "models" / "metrics.json") as f:
        metrics = json.load(f)
    return clf, reg, metrics


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def build_features(inputs):
    """Turn the form inputs into one row with the same columns used in training."""
    transport_score = {"Low": 2, "Medium": 6, "High": 10}[inputs["Public_Transport_Accessibility"]]
    row = {
        "City": inputs["City"],
        "Property_Type": inputs["Property_Type"],
        "BHK": inputs["BHK"],
        "Size_in_SqFt": inputs["Size_in_SqFt"],
        "Price_in_Lakhs": inputs["Price_in_Lakhs"],
        "Price_per_SqFt": round(inputs["Price_in_Lakhs"] * 100000 / inputs["Size_in_SqFt"], 2),
        "Age_of_Property": REFERENCE_YEAR - inputs["Year_Built"],
        "Floor_No": min(inputs["Floor_No"], inputs["Total_Floors"]),
        "Total_Floors": inputs["Total_Floors"],
        "Nearby_Schools": inputs["Nearby_Schools"],
        "Nearby_Hospitals": inputs["Nearby_Hospitals"],
        "Amenity_Count": len(inputs["Amenities"]),
        "School_Density_Score": inputs["Nearby_Schools"] / 10,
        "Infrastructure_Score": round((inputs["Nearby_Schools"] + inputs["Nearby_Hospitals"]
                                       + transport_score) / 3, 2),
        "Furnished_Status": inputs["Furnished_Status"],
        "Public_Transport_Accessibility": inputs["Public_Transport_Accessibility"],
        "Parking_Space": inputs["Parking_Space"],
        "Security": inputs["Security"],
        "Facing": inputs["Facing"],
        "Owner_Type": inputs["Owner_Type"],
        "Availability_Status": inputs["Availability_Status"],
    }
    for a in AMENITIES:
        row[f"Has_{a}"] = int(a in inputs["Amenities"])
    return pd.DataFrame([row])


def investment_checks(row, city_median_pps):
    """The five rules used to label Good Investment in the training data."""
    return [
        ("Price per sq ft at or below the city median "
         f"(₹{row['Price_per_SqFt']:,.0f} vs ₹{city_median_pps:,.0f})",
         row["Price_per_SqFt"] <= city_median_pps),
        ("3 or more BHK", row["BHK"] >= 3),
        ("Ready to move", row["Availability_Status"] == "Ready_to_Move"),
        ("Medium or High public transport access",
         row["Public_Transport_Accessibility"] in ("Medium", "High")),
        ("5 or more nearby schools", row["Nearby_Schools"] >= 5),
    ]


def feature_importance(pipe):
    """Importance per original feature, adding up the one-hot columns of each category."""
    names = pipe.named_steps["preprocessor"].get_feature_names_out()
    model = pipe.named_steps["model"]
    if hasattr(model, "feature_importances_"):
        values = model.feature_importances_
    else:  # linear models
        values = abs(model.coef_).ravel()

    def original_name(name):
        kind, rest = name.split("__", 1)
        if kind == "cat":
            for col in CATEGORICAL_FEATURES:
                if rest.startswith(col + "_"):
                    return col
        return rest

    imp = pd.Series(values, index=[original_name(n) for n in names]).groupby(level=0).sum()
    return (imp / imp.sum() * 100).sort_values(ascending=False)


def plot_importance(imp, title, color):
    top = imp.head(10).sort_values()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh(top.index, top.values, color=color)
    ax.set_title(title)
    ax.set_xlabel("Importance (%)")
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
df = load_data()
clf, reg, metrics = load_models()
city_medians = df.groupby("City")["Price_per_SqFt"].median()

st.title("🏠 Real Estate Investment Advisor")
st.caption("Predict whether a property is a good investment and estimate its price after 5 years.")

with st.sidebar:
    st.header("About")
    st.write(
        "This app uses two machine learning models trained on 250,000 property listings "
        "from 42 Indian cities:"
    )
    st.markdown(
        f"- **Classifier:** {metrics['classifier']['model'].replace('_', ' ')}\n"
        f"- **Regressor:** {metrics['regressor']['model'].replace('_', ' ')}"
    )
    st.info(
        "The dataset is synthetic, and both targets were created from documented rules "
        "(see the Model Insights tab). Predictions demonstrate the method and are not "
        "financial advice."
    )

tab_predict, tab_explore, tab_market, tab_model = st.tabs(
    ["🔮 Predict", "🔍 Explore Properties", "📊 Market Insights", "🧠 Model Insights"])

# ---------------------------- Predict tab ----------------------------------
with tab_predict:
    st.subheader("Enter property details")
    with st.form("predict_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            city = st.selectbox("City", sorted(df["City"].unique()))
            property_type = st.selectbox("Property Type", sorted(df["Property_Type"].unique()))
            bhk = st.selectbox("BHK", [1, 2, 3, 4, 5], index=2)
            size = st.number_input("Size (sq ft)", min_value=500, max_value=5000, value=1500, step=50)
            price = st.number_input("Current Price (Lakhs)", min_value=10.0, max_value=500.0,
                                    value=150.0, step=5.0)
        with c2:
            year_built = st.slider("Year Built", 1990, 2023, 2015)
            total_floors = st.slider("Total Floors in Building", 1, 30, 10)
            floor_no = st.slider("Floor Number", 0, 30, 3)
            furnished = st.selectbox("Furnished Status", ["Unfurnished", "Semi-furnished", "Furnished"])
            facing = st.selectbox("Facing", ["North", "East", "South", "West"])
        with c3:
            schools = st.slider("Nearby Schools", 1, 10, 5)
            hospitals = st.slider("Nearby Hospitals", 1, 10, 5)
            transport = st.selectbox("Public Transport Access", ["Low", "Medium", "High"], index=1)
            availability = st.selectbox("Availability", ["Ready_to_Move", "Under_Construction"])
            owner = st.selectbox("Listed by", ["Owner", "Builder", "Broker"])
        c4, c5, c6 = st.columns(3)
        with c4:
            amenities = st.multiselect("Amenities", AMENITIES, default=["Gym", "Pool"])
        with c5:
            parking = st.radio("Parking Space", ["Yes", "No"], horizontal=True)
        with c6:
            security = st.radio("Security", ["Yes", "No"], horizontal=True)
        submitted = st.form_submit_button("Predict", type="primary")

    if submitted:
        if floor_no > total_floors:
            st.warning(f"Floor number is higher than the building's total floors; "
                       f"using floor {total_floors} instead.")
        inputs = {
            "City": city, "Property_Type": property_type, "BHK": bhk, "Size_in_SqFt": size,
            "Price_in_Lakhs": price, "Year_Built": year_built, "Floor_No": floor_no,
            "Total_Floors": total_floors, "Furnished_Status": furnished, "Facing": facing,
            "Nearby_Schools": schools, "Nearby_Hospitals": hospitals,
            "Public_Transport_Accessibility": transport, "Availability_Status": availability,
            "Owner_Type": owner, "Amenities": amenities, "Parking_Space": parking,
            "Security": security,
        }
        X = build_features(inputs)
        prob_good = clf.predict_proba(X)[0][1]
        is_good = prob_good >= 0.5
        future_price = float(reg.predict(X)[0])
        total_growth = future_price / price - 1
        yearly_growth = (future_price / price) ** (1 / 5) - 1

        st.divider()
        r1, r2 = st.columns(2)
        with r1:
            st.subheader("Is this a Good Investment?")
            if is_good:
                st.success("✅ **Yes, Good Investment**")
            else:
                st.error("❌ **Not a Good Investment**")
            confidence = prob_good if is_good else 1 - prob_good
            st.metric("Model confidence", f"{confidence:.1%}")
            st.progress(float(confidence))
        with r2:
            st.subheader("Estimated Price after 5 Years")
            st.metric("Future price", f"₹{future_price:,.2f} Lakhs",
                      delta=f"{total_growth:+.1%} over 5 years")
            st.write(f"Current price: **₹{price:,.2f} Lakhs** · "
                     f"Implied yearly growth: **{yearly_growth:.1%}**")

        with st.expander("Why? See how this property scores on the investment criteria"):
            checks = investment_checks(X.iloc[0], city_medians[city])
            for label, passed in checks:
                st.write(("✅ " if passed else "❌ ") + label)
            st.write(f"**Score: {sum(p for _, p in checks)} / 5** "
                     "(3 or more was labelled Good Investment in the training data)")

# ---------------------------- Explore tab ----------------------------------
with tab_explore:
    st.subheader("Filter properties")
    f1, f2, f3 = st.columns(3)
    with f1:
        cities = st.multiselect("City", sorted(df["City"].unique()), placeholder="All cities")
        types = st.multiselect("Property Type", sorted(df["Property_Type"].unique()),
                               placeholder="All types")
    with f2:
        price_range = st.slider("Price (Lakhs)", 10, 500, (10, 500))
        size_range = st.slider("Size (sq ft)", 500, 5000, (500, 5000), step=100)
    with f3:
        bhks = st.multiselect("BHK", [1, 2, 3, 4, 5], placeholder="Any BHK")
        only_good = st.checkbox("Show only Good Investments")

    filtered = df[df["Price_in_Lakhs"].between(*price_range)
                  & df["Size_in_SqFt"].between(*size_range)]
    if cities:
        filtered = filtered[filtered["City"].isin(cities)]
    if types:
        filtered = filtered[filtered["Property_Type"].isin(types)]
    if bhks:
        filtered = filtered[filtered["BHK"].isin(bhks)]
    if only_good:
        filtered = filtered[filtered["Good_Investment"] == 1]

    m1, m2, m3 = st.columns(3)
    m1.metric("Matching properties", f"{len(filtered):,}")
    if len(filtered):
        m2.metric("Average price", f"₹{filtered['Price_in_Lakhs'].mean():,.1f} Lakhs")
        m3.metric("Good Investment rate", f"{filtered['Good_Investment'].mean():.1%}")
        show_cols = ["City", "Locality", "Property_Type", "BHK", "Size_in_SqFt",
                     "Price_in_Lakhs", "Price_per_SqFt", "Availability_Status",
                     "Future_Price_5Y", "Good_Investment"]
        st.dataframe(filtered[show_cols].head(500), width="stretch", hide_index=True)
        if len(filtered) > 500:
            st.caption("Showing the first 500 matching properties.")
    else:
        st.info("No properties match these filters. Try widening them.")

# ---------------------------- Market Insights tab --------------------------
with tab_market:
    st.subheader("Location-wise heatmap")
    metric_options = {
        "Average Price per Sq Ft (₹)": ("Price_per_SqFt", 1, ".0f"),
        "Average Price (Lakhs)": ("Price_in_Lakhs", 1, ".1f"),
        "Good Investment Rate (%)": ("Good_Investment", 100, ".1f"),
        "Average Yearly Growth Rate (%)": ("Growth_Rate", 100, ".2f"),
    }
    choice = st.selectbox("Metric", list(metric_options))
    col, scale, fmt = metric_options[choice]
    # Cities as columns and property types as rows, so the whole heatmap fits on one screen
    heat = (df.pivot_table(index="City", columns="Property_Type", values=col, aggfunc="mean")
            * scale).T
    fig, ax = plt.subplots(figsize=(18, 4))
    sns.heatmap(heat, annot=True, fmt=fmt, cmap="YlGnBu", ax=ax,
                annot_kws={"size": 7, "rotation": 90}, cbar_kws={"label": choice})
    ax.set_title(f"{choice} by City and Property Type")
    ax.set_xlabel("City")
    ax.set_ylabel("Property Type")
    plt.xticks(rotation=60, ha="right")
    plt.tight_layout()
    st.pyplot(fig)

    st.subheader("Price trend by construction year")
    trend_city = st.selectbox("City", ["All cities"] + sorted(df["City"].unique()), key="trend_city")
    trend_df = df if trend_city == "All cities" else df[df["City"] == trend_city]
    trend = (trend_df.groupby("Year_Built")[["Price_in_Lakhs", "Future_Price_5Y"]].mean()
             .rename(columns={"Price_in_Lakhs": "Current Price", "Future_Price_5Y": "Price after 5 Years"}))
    st.line_chart(trend, x_label="Year Built", y_label="Average Price (Lakhs)")

    st.subheader("Top 10 cities by Good Investment rate")
    top_cities = (df.groupby("City")["Good_Investment"].mean() * 100).nlargest(10)
    st.bar_chart(top_cities, x_label="City", y_label="Good Investment Rate (%)")

# ---------------------------- Model Insights tab ---------------------------
with tab_model:
    st.subheader("Model performance (test data: 50,000 properties)")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Accuracy", f"{metrics['classifier']['accuracy']:.2%}")
    k2.metric("F1-score", f"{metrics['classifier']['f1_score']:.4f}")
    k3.metric("RMSE", f"{metrics['regressor']['rmse']:.2f} Lakhs")
    k4.metric("MAE", f"{metrics['regressor']['mae']:.2f} Lakhs")
    k5.metric("R²", f"{metrics['regressor']['r2']:.5f}")

    t1, t2 = st.columns(2)
    with t1:
        st.write("**All classifiers compared**")
        st.dataframe(pd.DataFrame(metrics["all_classifiers"]).T, width="stretch")
        st.write("**Confusion matrix (best classifier)**")
        cm = pd.DataFrame(metrics["classifier"]["confusion_matrix"],
                          index=["Actual: Not Good", "Actual: Good"],
                          columns=["Predicted: Not Good", "Predicted: Good"])
        st.dataframe(cm, width="stretch")
    with t2:
        st.write("**All regressors compared**")
        st.dataframe(pd.DataFrame(metrics["all_regressors"]).T, width="stretch")

    st.subheader("Feature importance")
    i1, i2 = st.columns(2)
    i1.pyplot(plot_importance(feature_importance(clf), "Top 10 features: Good Investment", "#4C72B0"))
    i2.pyplot(plot_importance(feature_importance(reg), "Top 10 features: Future Price", "#DD8452"))

    with st.expander("How were the targets created?"):
        st.markdown(
            "**Good Investment:** a property scores 1 point for each condition met: price per "
            "sq ft at or below the city median, 3+ BHK, ready to move, Medium/High transport "
            "access, and 5+ nearby schools. A score of 3 or more is labelled Good Investment.\n\n"
            "**Future Price:** current price × (1 + r)⁵, where the yearly growth rate r starts "
            "at 8% and is adjusted for transport access (±1%), property age (±1%), "
            "4+ amenities (+0.5%) and security (+0.5%).\n\n"
            "Because the targets follow these rules, the models learn them almost perfectly, "
            "which explains the very high scores."
        )