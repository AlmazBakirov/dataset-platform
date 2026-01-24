import pandas as pd

path = r"storage\exports\requests\8\dataset.parquet"
df = pd.read_parquet(path)

pd.set_option("display.max_colwidth", None)
pd.set_option("display.width", 200)

print("COLUMNS:", list(df.columns))
print("ROWS:", len(df))

print("\n--- KEY FIELDS (FULL) ---")
print(
    df[["request_id", "image_id", "file_name", "storage_path"]].to_string(index=False)
)

print("\n--- LABELS (FULL) ---")
print(df[["image_id", "labels_json", "annotation_updated_at"]].to_string(index=False))

print("\n--- RAW LISTS ---")
print("storage_path list:", df["storage_path"].tolist())
print("labels_json list:", df["labels_json"].tolist())
