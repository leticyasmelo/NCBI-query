import streamlit as st
import requests
import pandas as pd
import re

# NCBI GEO query functions
@st.cache
def search_geo(term="single-cell RNA-seq", retmax=10000):
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
    return results.get("esearchresult", {}).get("idlist", []), int(results.get("esearchresult", {}).get("count", 0))

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
        
        # Extract cell count
        cell_count = "Unknown"
        sample_count = re.search(r"(\d[\d,]*) cells?", summary)
        if sample_count:
            cell_count = sample_count.group(1).replace(",", "")
        
        # Extract sequencing depth
        seq_depth = "Unknown"
        seq_match = re.search(r"sequencing depth of (\d[\d,]*)", summary.lower())
        if seq_match:
            seq_depth = seq_match.group(1).replace(",", "")
        
        datasets.append({
            "Dataset ID": value.get("uid"),
            "Title": title,
            "Cell Count": cell_count,
            "Sequencing Depth": seq_depth,
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
retmax = st.sidebar.number_input("Number of Results to Fetch", min_value=10, max_value=10000, value=1000, step=10)

# Fetch and display data
if st.button("Fetch Datasets"):
    with st.spinner("Querying NCBI GEO..."):
        geo_ids, total_count = search_geo(term=search_term, retmax=retmax)
        st.info(f"Found {total_count} datasets in total. Displaying up to {len(geo_ids)} datasets.")
        if not geo_ids:
            st.warning("No datasets found for the given query.")
        else:
            geo_metadata = fetch_geo_metadata(geo_ids)
            df = process_geo_metadata(geo_metadata)
            
            if df.empty:
                st.warning("No datasets could be processed.")
            else:
                st.success(f"Processed {len(df)} datasets.")
                
                # Filters for the dataset table
                st.sidebar.header("Filter Options")
                search_filter = st.sidebar.text_input("Search by Terms (e.g., macrophages)")
                if search_filter:
                    df = df[df["Summary"].str.contains(search_filter, case=False, na=False)]

                # Display the table
                st.write(f"### Filtered Datasets ({len(df)} results):")
                st.dataframe(df)

                # Option to download the filtered table
                @st.cache
                def convert_df_to_csv(dataframe):
                    return dataframe.to_csv(index=False).encode('utf-8')

                csv = convert_df_to_csv(df)
                st.download_button(
                    label="Download Filtered Table as CSV",
                    data=csv,
                    file_name="filtered_geo_datasets.csv",
                    mime="text/csv",
                )
