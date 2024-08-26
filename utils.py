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

from config import RELEVANT_COLUMNS, DATA_FILES

register_heif_opener()


def hash_f(x):
    return hashlib.md5(
        f"{x['Omschrijving']+str(x['Datum']) + str(float(x['Bedrag'].replace(',', '.')) / 1000)}".encode(encoding="latin-1")).hexdigest()


def load_data():
    data = []
    for file in DATA_FILES:
        data.append(pd.read_csv(file, delimiter=';', encoding='latin-1', usecols=RELEVANT_COLUMNS, decimal=","))

    df = pd.concat(data)
    df = df.drop_duplicates()

    df["Datum"] = pd.to_datetime(df["Datum"], format="%d/%m/%Y", dayfirst=True)

    # set bedrag column type to str

    df["Bedrag"] = df["Bedrag"].astype(str)

    df["hash"] = df.apply(hash_f, axis=1)
    df["Bedrag"] = df["Bedrag"].astype(float)

    df = assign_group(df)

    if os.path.exists("metadata.csv"):
        metadata = pd.read_csv("metadata.csv", encoding="latin-1")

        df = df.merge(metadata, on="hash", how="left")
        df.drop_duplicates(inplace=True)
        df = df.drop(columns=["hash"])

        df["Category"] = df["Category"].astype(str)
        df["Category"] = df["Category"].fillna("Other")
        df["Split with Medha"] = df["Split with Medha"].astype(bool)

    else:
        df["Category"] = "Other"
        df["Category"] = df["Category"].astype(str)
        df["Split with Medha"] = False
        df["Split with Medha"] = df["Split with Medha"].astype(bool)

    date_match = df["Omschrijving"].str.extract(r"(\d{2}-\d{2}-\d{4}) OM (\d{2}\.\d{2}) UUR")
    df["Actual Date"] = pd.to_datetime(date_match[0] + " " + date_match[1], format="%d-%m-%Y %H.%M", errors="coerce").combine_first(df["Datum"])

    return df


@st.cache_data
def download_photos(start_date, end_date):
    start_date = start_date.strftime("%Y-%m-%d")
    end_date = end_date.strftime("%Y-%m-%d")

    subprocess.call(["gphotos-sync", "./photos", "--start-date", start_date, "--end-date",
                     end_date, "--use-flat-path", "--skip-video", "--skip-shared-albums"])


def assign_group(df):
    filtered_text = df["Omschrijving"].str.lower().str.replace(r"[a-f0-9]{3,}", " ", regex=True)
    filtered_text = filtered_text.str.replace(r"[^a-z]", " ", regex=True)
    df["group"] = filtered_text.apply(lambda x: hashlib.md5(x.encode()).hexdigest())
    return df


@ st.cache_data
def parse_timeline_data():
    locations = json.load(open("location-history.json"))

    rows = []
    for location in locations:

        start_time = location["startTime"]
        start_time = pd.to_datetime(start_time)

        geo_points_text = json.dumps(location, indent=4)

        geo_points_match = re.search(r"geo:(?P<lat>.+?),(?P<lon>.+)\"", geo_points_text)

        if geo_points_match:
            lat = geo_points_match.group("lat")
            lon = geo_points_match.group("lon")
            rows.append({"start_time": start_time, "lat": float(lat), "lon": float(lon)})

    return rows


def load_timeline_data():

    rows = parse_timeline_data()

    st.session_state["full_location_df"] = pd.DataFrame(rows)
    st.session_state["full_location_df"]["start_time"] = pd.to_datetime(st.session_state["full_location_df"]["start_time"], utc=True)


def filter_map_data(date):

    location_df = st.session_state["full_location_df"].copy()
    location_df = location_df[location_df["start_time"].dt.date == date.date()]

    if len(location_df) == 0:
        if "location_df" in st.session_state:
            del st.session_state["location_df"]
        return

    st.session_state["location_df"] = location_df


def filter_images(date):
    images = []
    download_photos(date, date + pd.Timedelta(days=1))
    image_dir = pathlib.Path("photos") / "photos"

    for image_file in image_dir.glob("*/*"):
        with image_file.open("rb") as f:
            if image_file.suffix == ".PNG":
                continue
            tags = exifread.process_file(f, details=False)

            if "Image DateTime" in tags:
                image_date = tags["Image DateTime"]
                image_date = pd.to_datetime(str(image_date), format="%Y:%m:%d %H:%M:%S")
                if image_date.date() == date.date():
                    images.append((image_file, image_date))

    if len(images) == 0:
        if "selected_images" in st.session_state:
            del st.session_state["selected_images"]
        return
    else:
        st.session_state["selected_images"] = images


def filter_calendar_events(date):
    events = get_events(date)
    if len(events) == 0:
        if "calendar_events" in st.session_state:
            del st.session_state["calendar_events"]
        return
    else:

        events = [(event[0], pd.to_datetime(event[1])) for event in events]
        st.session_state["calendar_events"] = events


def update_dataframe():
    category = st.session_state["category_dropdown"]
    split_with_medha = st.session_state["Split with Medha"]
    st.session_state.df.loc[st.session_state["selected_row"].name, "Category"] = category
    st.session_state.df.loc[st.session_state["selected_row"].name, "Split with Medha"] = split_with_medha


def display_row(selected_row):
    cols = RELEVANT_COLUMNS.copy()
    cols.remove("Datum")
    cols.insert(0, "Actual Date")
    st.session_state["selected_row_dict"] = selected_row[cols].to_dict()

    filter_map_data(selected_row["Actual Date"])
    filter_images(selected_row["Actual Date"])
    filter_calendar_events(selected_row["Actual Date"])

    selected_row_idx = selected_row.name
    similar_rows = st.session_state.df[st.session_state.df["group"] == selected_row["group"]]
    similar_rows = similar_rows[similar_rows.index != selected_row_idx]

    if len(similar_rows) > 0:
        st.session_state["similar_rows"] = similar_rows
    else:
        if "similar_rows" in st.session_state:
            del st.session_state["similar_rows"]


def show_entry_on_click():

    selected_rows_idx = st.session_state["dataframe"]["selection"]["rows"]

    if len(selected_rows_idx) == 0:
        return
    selected_row_idx = selected_rows_idx[0]
    selected_row = st.session_state.df.iloc[selected_row_idx]
    st.session_state["selected_row"] = selected_row
    display_row(selected_row)


def apply_to_all():
    category = st.session_state["category_dropdown"]
    split_with_medha = st.session_state["Split with Medha"]

    for idx, _ in st.session_state["similar_rows"].iterrows():
        st.session_state.df.loc[idx, "Category"] = category
        st.session_state.df.loc[idx, "Split with Medha"] = split_with_medha

    save_dataframe()
    move_to_next_row()


def move_to_next_row():
    st.session_state.df.sort_values(by="Actual Date", inplace=True)
    if "Other" in st.session_state.df["Category"].values:
        st.session_state["selected_row"] = st.session_state.df[st.session_state.df["Category"] == "Other"].iloc[0]
    else:
        st.session_state["selected_row"] = st.session_state.df.loc[st.session_state["selected_row"].name + 1]
    selected_row = st.session_state["selected_row"]
    display_row(selected_row)


def save_dataframe():
    df: pd.DataFrame = st.session_state.df.copy()
    print("storing metadata", len(df))
    df["Bedrag"] = df["Bedrag"].astype(str)

    df["hash"] = df.apply(hash_f, axis=1)
    df.drop(columns=RELEVANT_COLUMNS + ["Actual Date", "group"]).to_csv("metadata.csv", index=False, encoding="latin-1", decimal=",")


def apply_single_row():
    save_dataframe()
    move_to_next_row()


def export():
    df = st.session_state.df.copy()
    df["Datum"] = df["Datum"].dt.strftime("%d/%m/%Y")
    df.drop(columns=["group", "Actual Date"], inplace=True)
    df["Split with Medha"] = df["Split with Medha"].astype(int)
    df.to_csv(f"export.csv", sep=";", encoding="latin-1", index=False)
