import pandas as pd

splits = {'train': 'train.csv', 'validation': 'valid.csv', 'test': 'test.csv'}

# load the test split
df_test = pd.read_csv("hf://datasets/chengxuphd/liar2/" + splits["test"])

# save it out so you can open it in Excel / a text editor / etc.
df_test.to_csv("dataset/liar2_test.csv", index=False)