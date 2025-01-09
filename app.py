import streamlit as st
import requests
import pandas as pd
import re

# NCBI GEO query functions
@st.cache
def search_geo(term="single-cell RNA-seq", retmax=50):
    """Query GEO for datasets matching the given term."""
    GEO_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "gds",
        "term": term,
        "retmax": retmax,
        "retmode": "json",
    }
    response = requests.get(GEO_BASE_URL, params=params)
    response.raise_for_status()
    results = response.json()
    return results.get("esearchresult", {}).get("idlist", [])

@st.cache
def fetch_geo_metadata(geo_ids):
    """Fetch metadata for given GEO dataset IDs."""
    GEO_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = {
        "db": "gds",
        "id": ",".join(geo_ids),
        "retmode": "json",
    }
    response = requests.get(GEO_SUMMARY_URL, params=params)
    response.raise_for_status()
    return response.json().get("result", {})

@st.cache
def process_geo_metadata(geo_metadata):
    """Process GEO metadata to extract relevant dataset information."""
    datasets = []
    for key, value in geo_metadata.items():
        if key == "uids":
            continue
        title = value.get("title", "N/A")
        summary = value.get("summary", "N/A")
        sample_count = re.search(r"(\d+) cells?", summary)
        cell_count = int(sample_count.group(1)) if sample_count else "Unknown"
        is_time_series = "time" in summary.lower()
        is_linear = "differentiation" in summary.lower() or "linear" in summary.lower()
        is_branched = "branch" in summary.lower() or "cyclic" in summary.lower()
        datasets.append({
            "Dataset ID": value.get("uid"),
            "Title": title,
            "Cell Count": cell_count,
            "Conditions": "Multiple" if "healthy" in summary.lower() and "disease" in summary.lower() else "Single",
            "Trajectory Type": "Linear" if is_linear else "Branched" if is_branched else "Unknown",
            "Time-Series": "Yes" if is_time_series else "No",
            "Summary": summary,
        })
    return pd.DataFrame(datasets)

# Streamlit app
st.title("NCBI GEO Single-Cell Dataset Explorer")
st.markdown("""
This app queries the NCBI GEO database for single-cell RNA-seq datasets and allows you to filter and explore the results.
""")

# Sidebar inputs for query and result limits
search_term = st.sidebar.text_input("Search Term", value="single-cell RNA-seq")
retmax = st.sidebar.slider("Number of Results", min_value=10, max_value=100, value=50)

# Fetch and display data
if st.button("Fetch Datasets"):
    with st.spinner("Querying NCBI GEO..."):
        geo_ids = search_geo(term=search_term, retmax=retmax)
        if not geo_ids:
            st.warning("No datasets found for the given query.")
        else:
            geo_metadata = fetch_geo_metadata(geo_ids)
            df = process_geo_metadata(geo_metadata)
            
            if df.empty:
                st.warning("No datasets could be processed.")
            else:
                st.success(f"Found {len(df)} datasets.")
                
                # Filters for the dataset table
                st.sidebar.header("Filter Options")
                conditions = st.sidebar.multiselect(
                    "Select Conditions", df["Conditions"].unique(), default=df["Conditions"].unique()
                )
                trajectory_type = st.sidebar.multiselect(
                    "Select Trajectory Type", df["Trajectory Type"].unique(), default=df["Trajectory Type"].unique()
                )
                time_series = st.sidebar.selectbox("Is it Time-Series?", ["All", "Yes", "No"], index=0)

                # Apply filters
                filtered_df = df[
                    (df["Conditions"].isin(conditions)) &
                    (df["Trajectory Type"].isin(trajectory_type))
                ]
                if time_series != "All":
                    filtered_df = filtered_df[filtered_df["Time-Series"] == time_series]

                # Display the table
                st.write(f"### Filtered Datasets ({len(filtered_df)} results):")
                st.dataframe(filtered_df)

                # Option to download the filtered table
                @st.cache
                def convert_df_to_csv(dataframe):
                    return dataframe.to_csv(index=False).encode('utf-8')

                csv = convert_df_to_csv(filtered_df)
                st.download_button(
                    label="Download Filtered Table as CSV",
                    data=csv,
                    file_name="filtered_geo_datasets.csv",
                    mime="text/csv",
                )


