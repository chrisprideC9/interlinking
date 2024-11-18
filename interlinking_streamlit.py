import streamlit as st
import pandas as pd
from urllib.parse import urlparse
from collections import Counter
from io import BytesIO

def extract_main_domain(url):
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    return domain

def process_data(df):
    # Extract domains from the "Source" column
    if 'Source' not in df.columns:
        st.error("The uploaded CSV does not contain a 'Source' column.")
        return None, None
    
    domains = df['Source'].apply(extract_main_domain)

    # Find the most common domain
    domain_counts = Counter(domains)
    if not domain_counts:
        st.error("No domains found in the 'Source' column.")
        return None, None
    
    main_domain = domain_counts.most_common(1)[0][0]
    st.success(f"Main domain detected: {main_domain}")

    # Drop the specified columns
    columns_to_drop_initial = ['Size (Bytes)', 'Alt Text', 'Status', 'Type']
    existing_columns_to_drop_initial = [col for col in columns_to_drop_initial if col in df.columns]
    df = df.drop(columns=existing_columns_to_drop_initial)

    # Drop the range of columns from 'Follow' to 'Link Path'
    if 'Follow' in df.columns and 'Link Path' in df.columns:
        columns_to_drop = df.loc[:, 'Follow':'Link Path'].columns
        df = df.drop(columns=columns_to_drop)

    # Filter rows where 'Link Position' is 'Content'
    if 'Link Position' in df.columns:
        df = df[df['Link Position'] == 'Content']
    else:
        st.warning("Column 'Link Position' not found. Skipping this filter.")

    # Drop the columns 'Link Origin' and 'Link Position'
    columns_to_drop_final = ['Link Origin', 'Link Position']
    existing_columns_to_drop_final = [col for col in columns_to_drop_final if col in df.columns]
    df = df.drop(columns=existing_columns_to_drop_final)

    # Filter rows where 'Destination' contains the main domain
    if 'Destination' in df.columns:
        df = df[df['Destination'].str.contains(main_domain, na=False)]
    else:
        st.error("The uploaded CSV does not contain a 'Destination' column.")
        return None, None

    # Separate rows with status code 200
    if 'Status Code' in df.columns:
        df_status_200 = df[df['Status Code'] == 200]
        df_other_status = df[df['Status Code'] != 200]
    else:
        st.warning("Column 'Status Code' not found. Skipping status code filtering.")
        df_status_200 = df.copy()
        df_other_status = pd.DataFrame()

    # Remove the 'Status Code' column from df_status_200
    if 'Status Code' in df_status_200.columns:
        df_status_200 = df_status_200.drop(columns=['Status Code'])

    # Remove duplicates based on 'Source' and 'Destination' columns
    df_status_200 = df_status_200.drop_duplicates(subset=['Source', 'Destination'])

    # List of unwanted extensions
    unwanted_extensions = [
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', 
        '.mp4', '.avi', '.mov', '.wmv', '.flv', 
        '.mp3', '.wav', '.ogg', 
        '.js', '.css', '.pdf', '.doc', '.docx'
    ]

    # Filter out rows where 'Destination' URLs end with unwanted extensions
    if 'Destination' in df_status_200.columns:
        df_status_200 = df_status_200[~df_status_200['Destination'].str.lower().str.endswith(tuple(unwanted_extensions))]
    else:
        st.error("The 'Destination' column is missing.")
        return None, None

    # Drop any rows where the value of 'Anchor' is nothing
    if 'Anchor' in df_status_200.columns:
        df_status_200 = df_status_200[(df_status_200['Anchor'].notna()) & (df_status_200['Anchor'] != '')]
    else:
        st.warning("Column 'Anchor' not found. Skipping this filter.")

    # Drop any rows where the value of anchor occurs more than 5 times.
    if 'Anchor' in df_status_200.columns:
        anchor_counts = df_status_200['Anchor'].value_counts()
        df_status_200 = df_status_200[~df_status_200['Anchor'].isin(anchor_counts[anchor_counts > 5].index)]
    else:
        st.warning("Column 'Anchor' not found. Skipping this filter.")

    # Remove rows where 'Source' matches 'Destination'
    df_status_200 = df_status_200[df_status_200['Source'] != df_status_200['Destination']]

    # Add a new column 'unique_urls' which is a copy of the 'Destination' column
    df_status_200['unique_urls'] = df_status_200['Destination']

    # Get unique URLs and their counts in the Destination column
    unique_urls_counts = df_status_200['Destination'].value_counts().reset_index()
    unique_urls_counts.columns = ['unique_urls', 'count']

    # Drop the 'unique_urls' column from df_status_200
    df_status_200 = df_status_200.drop(columns=['unique_urls'])

    # Sort df_status_200 alphabetically by the 'Source' column
    df_status_200 = df_status_200.sort_values(by='Source')

    return df_status_200, unique_urls_counts

def to_excel(df_cleaned, df_unique):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_cleaned.to_excel(writer, sheet_name='Cleaned Data', index=False)
        df_unique.to_excel(writer, sheet_name='Unique URLs Counts', index=False)
    processed_data = output.getvalue()
    return processed_data

def main():
    st.title("CSV Processor with Streamlit")
    st.write("""
        Upload a CSV file, and this app will process it to extract the main domain,
        clean the data, and provide a downloadable Excel file with the results.
    """)

    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.success("File uploaded successfully!")
            st.write("### Preview of Uploaded Data:")
            st.dataframe(df.head())

            if st.button("Process Data"):
                with st.spinner("Processing..."):
                    df_cleaned, df_unique = process_data(df)
                    if df_cleaned is not None and df_unique is not None:
                        excel_data = to_excel(df_cleaned, df_unique)
                        st.success("Data processed successfully!")

                        st.write("### Download Processed Data:")
                        st.download_button(
                            label="Download Excel File",
                            data=excel_data,
                            file_name='output_data.xlsx',
                            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        )

                        st.write("### Cleaned Data:")
                        st.dataframe(df_cleaned)

                        st.write("### Unique URLs Counts:")
                        st.dataframe(df_unique)
        except Exception as e:
            st.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
