import streamlit as st
import requests
import pandas as pd
import re
import time

# NCBI GEO query functions
@st.cache_data
def search_geo(retmax=10000):
    """Query GEO for datasets matching scRNA-seq-related terms."""
    # Combine search terms with OR for broader search
    term = "scRNA-seq OR single-cell RNAseq OR scRNAseq"
    
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
    return results.get("esearchresult", {}).get("idlist", []), int(results.get("esearchresult", {}).get("count", 0))

@st.cache_data
def fetch_geo_metadata(geo_ids, chunk_size=50):
    """Fetch metadata for given GEO dataset IDs in chunks with error handling."""
    GEO_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    results = {}
    for i in range(0, len(geo_ids), chunk_size):
        chunk = geo_ids[i:i + chunk_size]
        params = {
            "db": "gds",
            "id": ",".join(chunk),
            "retmode": "json",
        }
        try:
            response = requests.get(GEO_SUMMARY_URL, params=params)
            response.raise_for_status()
            chunk_results = response.json().get("result", {})
            results.update(chunk_results)
        except requests.exceptions.HTTPError as e:
            st.error(f"HTTPError: {e} for chunk {chunk}")
            continue  # Skip the problematic chunk
        except Exception as e:
            st.error(f"Unexpected error: {e} for chunk {chunk}")
            continue
        time.sleep(0.5)  # Delay to avoid rate limits
    return results

@st.cache_data
def process_geo_metadata(geo_metadata):
    """Process GEO metadata to extract relevant dataset information."""
    datasets = []
    for key, value in geo_metadata.items():
        if key == "uids":
            continue
        title = value.get("title", "N/A")
        summary = value.get("summary", "N/A")

        # Extract GEO Accession Number
        geo_number = value.get("accession", "N/A")
        
        # Extract species and clean formatting
        species = "Unknown"
        species_list = value.get("taxon", [])
        if species_list:
            species = " ".join("".join(species_list).split())  # Properly format species

        # Include datasets based on relevant terms
        if not any(term in summary.lower() for term in ["single-cell", "scrnaseq", "scrna-seq"]):
            continue

        # Check if study is longitudinal
        longitudinal = "No"
        if any(keyword in summary.lower() for keyword in ["longitudinal", "time points", "day", "week", "month"]):
            longitudinal = "Yes"

        datasets.append({
            "GEO Number": geo_number,
            "Title": title,
            "Species": species,
            "Longitudinal Study": longitudinal,
            "Summary": summary,
        })
    return pd.DataFrame(datasets)

# Initialize session state for filters
if "data" not in st.session_state:
    st.session_state["data"] = None  # To store processed data

if "search_filter" not in st.session_state:
    st.session_state["search_filter"] = ""

if "species_filter" not in st.session_state:
    st.session_state["species_filter"] = ""

if "longitudinal_filter" not in st.session_state:
    st.session_state["longitudinal_filter"] = "All"

# Streamlit app
st.title("NCBI GEO Single-Cell Dataset Explorer")
st.markdown("""
This app queries the NCBI GEO database for single-cell RNA-seq datasets using the terms `scRNA-seq`, `single-cell RNAseq`, and `scRNAseq` for a broad search. You can apply filters to refine the results.
""")

# Sidebar inputs for result limits
retmax = st.sidebar.number_input("Number of Results to Fetch", min_value=10, max_value=10000, value=1000, step=10)

# Fetch and display data
if st.button("Fetch Datasets"):
    with st.spinner("Querying NCBI GEO..."):
        geo_ids, total_count = search_geo(retmax=retmax)
        st.info(f"Found {total_count} datasets in total. Displaying up to {len(geo_ids)} datasets.")
        if not geo_ids:
            st.warning("No datasets found for the given query.")
        else:
            geo_metadata = fetch_geo_metadata(geo_ids)
            st.session_state["data"] = process_geo_metadata(geo_metadata)
            
            if st.session_state["data"].empty:
                st.warning("No datasets could be processed.")
            else:
                st.success(f"Processed {len(st.session_state['data'])} datasets.")

# Filters for the dataset table
if st.session_state["data"] is not None:
    st.sidebar.header("Filter Options")
    st.session_state["search_filter"] = st.sidebar.text_input(
        "Search by Terms (e.g., macrophages)", value=st.session_state["search_filter"]
    )
    st.session_state["species_filter"] = st.sidebar.text_input(
        "Filter by Species (e.g., human, mouse)", value=st.session_state["species_filter"]
    )
    st.session_state["longitudinal_filter"] = st.sidebar.selectbox(
        "Filter by Longitudinal Study",
        options=["All", "Yes", "No"],
        index=["All", "Yes", "No"].index(st.session_state["longitudinal_filter"]),
    )

    # Apply filters
    df = st.session_state["data"].copy()
    if st.session_state["search_filter"]:
        df = df[df["Summary"].str.contains(st.session_state["search_filter"], case=False, na=False)]
    if st.session_state["species_filter"]:
        df = df[df["Species"].str.contains(st.session_state["species_filter"], case=False, na=False)]
    if st.session_state["longitudinal_filter"] != "All":
        df = df[df["Longitudinal Study"] == st.session_state["longitudinal_filter"]]

    # Display the table
    st.write(f"### Filtered Datasets ({len(df)} results):")
    st.dataframe(df)

    # Option to download the filtered table
    @st.cache_data
    def convert_df_to_csv(dataframe):
        return dataframe.to_csv(index=False).encode('utf-8')

    csv = convert_df_to_csv(df)
    st.download_button(
        label="Download Filtered Table as CSV",
        data=csv,
        file_name="filtered_geo_datasets.csv",
        mime="text/csv",
    )
