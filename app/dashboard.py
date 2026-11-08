"""Streamlit dashboard: pick one of the questions, see the answer as a chart and a table.

Every time the page is opened or a question is chosen, Streamlit runs this file from the top.
The questions themselves (title and SQL) are in common/queries.py.
"""
import sys
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so "common" is found
from common.db import connect  # noqa: E402
from common.queries import QUERIES  # noqa: E402


@st.cache_resource
def get_conn():
    """One connection for the whole app, instead of a new one at every click."""
    return connect()


def run(sql: str) -> tuple[pd.DataFrame, float]:
    """Run a query and return the result as a table, with how long it took in seconds."""
    conn = get_conn()
    t0 = time.perf_counter()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [d.name for d in cur.description]
    finally:
        # we only read: close the transaction so the connection stays clean. In "finally" so it
        # also runs when the query fails; otherwise the shared connection would stay in an
        # aborted transaction and every later query would fail until the app is restarted.
        conn.rollback()
    return pd.DataFrame(rows, columns=cols), time.perf_counter() - t0


def is_number(col: pd.Series) -> bool:
    return pd.to_numeric(col, errors="coerce").notna().all()


# ---------------------------------------------------------------- header
st.set_page_config(page_title="Spotify tracks", layout="wide")
st.title("What makes a track popular on Spotify?")
st.caption("Spotify Tracks dataset (114 genres), stored in PostgreSQL")

counts, _ = run("SELECT (SELECT COUNT(*) FROM track)  AS tracks, "
                "(SELECT COUNT(*) FROM artist)        AS artists, "
                "(SELECT COUNT(*) FROM genre)         AS genres")
c1, c2, c3 = st.columns(3)
c1.metric("Tracks", f"{counts.at[0, 'tracks']:,}")
c2.metric("Artists", f"{counts.at[0, 'artists']:,}")
c3.metric("Genres", f"{counts.at[0, 'genres']:,}")

# ---------------------------------------------------------------- the chosen question
choice = st.selectbox("Question", list(QUERIES), format_func=lambda k: f"{k}. {QUERIES[k][0]}")
title, sql = QUERIES[choice]
df, seconds = run(sql)

st.subheader(title)
st.caption(f"{len(df)} rows · query took {seconds * 1000:.1f} ms")

# Bar chart: the first text column gives the labels, the last number column the bar length
# (the queries are written so that the main result is their last column).
numeric = [c for c in df.columns if is_number(df[c])]
texts = [c for c in df.columns if not is_number(df[c])]
if texts and numeric and len(df) > 1:
    label, value = texts[0], numeric[-1]
    chart = df[[label, value]].assign(**{value: pd.to_numeric(df[value])})
    # two rows with the same label (the same title on two albums) would be drawn as one bar,
    # so in that case we add the next text column to the label
    if chart[label].duplicated().any() and len(texts) > 1:
        chart[label] = df[label] + " (" + df[texts[1]].str.slice(0, 25) + ")"
    st.altair_chart(alt.Chart(chart).mark_bar().encode(
        x=alt.X(value, type="quantitative"),
        y=alt.Y(label, type="nominal", sort="-x"),
        tooltip=[label, value]), use_container_width=True)

st.dataframe(df, use_container_width=True, hide_index=True)
with st.expander("SQL"):
    st.code(sql.strip(), language="sql")
