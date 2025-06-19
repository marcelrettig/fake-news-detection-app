#!/usr/bin/env python3
"""
dataset_cleaner.py

Reads a CSV and writes out only those rows where:
  • both the 'text' and 'title' columns are truly non-empty
  • the 'title' column does NOT contain the word "video" (in any casing).

Paths and column names are hardcoded below.
"""

import pandas as pd

# ─── CONFIG ─────────────────────────────────────────────────────────────────────
INPUT_CSV   = 'dataset/Fake.csv'
OUTPUT_CSV  = 'dataset/FilteredFake.csv'
TEXT_COL    = 'text'
TITLE_COL   = 'title'
# ────────────────────────────────────────────────────────────────────────────────

def filter_and_remove_videos():
    # 1) load everything as strings
    df = pd.read_csv(INPUT_CSV, dtype=str)

    # 2) sanity check
    for col in (TEXT_COL, TITLE_COL):
        if col not in df.columns:
            raise KeyError(f"Column '{col}' not found. Available: {list(df.columns)}")

    # 3) normalize whitespace & strip
    df[TEXT_COL]  = (
        df[TEXT_COL]
        .fillna('')
        .astype(str)
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
    )
    df[TITLE_COL] = (
        df[TITLE_COL]
        .fillna('')
        .astype(str)
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
    )

    # 4a) filter out empty text & titles
    mask_nonempty = (df[TEXT_COL] != '') & (df[TITLE_COL] != '')

    # 4b) filter out any title containing the word "video" (case-insensitive, whole word)
    mask_no_video = ~df[TITLE_COL].str.contains(r'\bvideo\b', case=False, na=False)

    # 4c) combine both masks
    filtered = df[mask_nonempty & mask_no_video]

    # 5) save result
    filtered.to_csv(OUTPUT_CSV, index=False)
    total, kept = len(df), len(filtered)
    print(f"Wrote {kept} / {total} rows to {OUTPUT_CSV}; dropped {total - kept} rows "
          f"(empty text/title or title containing “video”).")

if __name__ == '__main__':
    filter_and_remove_videos()
