import pandas as pd

# load the test split
df = pd.read_csv("dataset/liar2_test.csv")

# build a boolean mask: context contains “tweet” or “twitter” (case‐insensitive)
mask = df['context'].str.contains(r'\b(?:tweet|twitter|facebook)\b', case=False, na=False)

# apply the mask
df_filtered = df[mask]

# save filtered rows to a new CSV
df_filtered.to_csv("dataset_samples/liar2_test_tweet.csv", index=False)
