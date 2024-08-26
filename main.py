import pathlib
import streamlit as st
import os
import pandas as pd
import hashlib
import json
import re
from PIL import Image
from pillow_heif import register_heif_opener
import exifread
import subprocess
from calendar_api import get_events
import config as cfg
import plotly.express as px


import utils


st.set_page_config(layout="wide")


def init():
    if "df" not in st.session_state:
        st.session_state.df = utils.load_data()
        st.session_state.df.sort_values(by="Category", key=lambda x: x != "Other", inplace=True)

        utils.load_timeline_data()


if __name__ == "__main__":
    init()

    st.button("export", on_click=utils.export)

    if "Other" in st.session_state.df["Category"].value_counts():
        st.write((len(st.session_state.df) - st.session_state.df["Category"].value_counts()["Other"]), "/", len(st.session_state.df))
        st.progress(1 - (st.session_state.df["Category"].value_counts()["Other"] / len(st.session_state.df)))
    else:
        st.write(len(st.session_state.df), "/", len(st.session_state.df))
        st.progress(1)

    columns = st.columns(3)

    with columns[0]:

        with st.container(height=300):

            st.dataframe(
                st.session_state.df,
                on_select=utils.show_entry_on_click,
                selection_mode="single-row",
                key="dataframe",
                column_order=["Actual Date"] + cfg.ADDED_COLUMNS + cfg.RELEVANT_COLUMNS,
            )

        st.plotly_chart(
            # absolute values
            px.line(st.session_state.df.sort_values(by="Datum"), x="Datum", y="Saldo", title="Saldo over time")
        )

        st.write(
            st.session_state.df[st.session_state.df["Bedrag"] > 0]["Bedrag"].groupby(st.session_state.df["Category"]).sum()
        )

        st.write(
            st.session_state.df[st.session_state.df["Bedrag"] < 0]["Bedrag"].groupby(st.session_state.df["Category"]).sum()
        )
        pie_chart = px.pie(st.session_state.df[st.session_state.df["Bedrag"] < 0], names="Category",
                           title="Category distribution")

        pie_chart.update_traces(textinfo='value')

        st.plotly_chart(
            pie_chart
        )

        pie_chart = px.pie(st.session_state.df[st.session_state.df["Bedrag"] > 0], names="Category",
                           title="Category distribution")

        pie_chart.update_traces(textinfo='value')

        st.plotly_chart(
            pie_chart
        )

    with columns[1]:

        if "selected_row_dict" in st.session_state:

            st.selectbox("Category",
                         cfg.CATEGORY_OPTIONS,
                         index=cfg.CATEGORY_OPTIONS.index(st.session_state["selected_row"]["Category"]),
                         key="category_dropdown",
                         on_change=utils.update_dataframe,
                         )

            st.checkbox("Split with Medha",
                        key="Split with Medha",
                        value=st.session_state["selected_row"]["Split with Medha"],
                        on_change=utils.update_dataframe
                        )
            for k, v in st.session_state["selected_row_dict"].items():
                v = str(v).strip()
                if v not in [None, ""]:
                    st.write(f"{v}")

            cols = st.columns(2)

            with cols[0]:
                st.button("apply", on_click=utils.apply_single_row)

            with cols[1]:
                if "similar_rows" in st.session_state:
                    st.button("apply to all", on_click=utils.apply_to_all)

            if "similar_rows" in st.session_state:

                st.dataframe(st.session_state["similar_rows"],
                             column_order=["Actual Date"] + cfg.ADDED_COLUMNS + cfg.RELEVANT_COLUMNS)

    with columns[2]:

        if "calendar_events" in st.session_state:
            with st.container(height=100):
                st.write("Calendar events")
                for event in st.session_state["calendar_events"]:
                    st.text(f"- {event[0]} : {event[1].strftime('%H:%M')}")

        if "selected_images" in st.session_state:

            with st.container(height=200):
                columns = st.columns(3)

                images = st.session_state["selected_images"]

                for i, (image, image_date) in enumerate(images):
                    with columns[i % 3]:
                        st.write(image_date)
                        st.image(Image.open(image))

        if "location_df" in st.session_state:
            with st.container(height=400):

                st.map(st.session_state["location_df"], size=5)
