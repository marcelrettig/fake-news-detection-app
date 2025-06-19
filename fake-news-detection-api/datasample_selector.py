import pandas as pd

df = pd.read_csv("dataset/FilteredFake.csv")
df.sample(n=100, random_state=42).to_csv("dataset_samples/sample100.csv", index=False)
