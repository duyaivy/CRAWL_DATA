import pandas as pd
import requests
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import random
import os
import argparse

def check_url(url):
    """Checks if a Cloudinary URL is valid (returns 200)."""
    try:
        # Cloudinary returns 404 if the image is deleted
        response = requests.head(url, timeout=5, allow_redirects=True)
        return response.status_code == 200
    except Exception:
        return False

def process_csv(file_path, shuffle=True):
    """Processes the CSV: validates URLs and optionally shuffles rows."""
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    print(f"Reading {file_path}...")
    
    # Use csv module for more robust reading of potentially malformed rows
    import csv
    data = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            header = next(reader)
            # Only take the first 3 columns even if more exist
            clean_header = header[:3]
            for row in reader:
                if row:
                    data.append(row[:3])
        df = pd.DataFrame(data, columns=clean_header)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return


    if shuffle:
        print("Randomizing row order (skipping validation)...")
        df_clean = df.sample(frac=1).reset_index(drop=True)
    else:
        urls = df.iloc[:, 1].tolist() # Assuming second column is the URL
        print(f"Checking {len(urls)} URLs for validity (skipping randomization)...")
        # Using ThreadPoolExecutor for parallel network requests
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(tqdm(executor.map(check_url, urls), total=len(urls), desc="Validating"))
        
        # Filter broken links
        df['is_valid'] = results
        initial_count = len(df)
        df_clean = df[df['is_valid'] == True].copy()
        df_clean.drop(columns=['is_valid'], inplace=True)
        final_count = len(df_clean)
        print(f"Removed {initial_count - final_count} broken links.")
    
    # Save back to the same file
    df_clean.to_csv(file_path, index=False)
    print(f"Success! Updated {file_path}. Final row count: {len(df_clean)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean broken Cloudinary links and shuffle CSV rows.")
    parser.add_argument("file", help="Path to the CSV file (e.g., cloudinary_links/vay.csv)")
    parser.add_argument("--random", action="store_true", default=False, help="Enable randomization of row order")
    
    args = parser.parse_args()
    
    process_csv(args.file, shuffle=args.random)
