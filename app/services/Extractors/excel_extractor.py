import pandas as pd

def extract_from_excel(file_path):
    dfs = pd.read_excel(file_path, sheet_name=None)
    documents = []
    for sheet_name, df in dfs.items():
        # هر سطر را به یک رشته قابل فهم تبدیل کن
        for index, row in df.iterrows():
            row_text = f"Sheet: {sheet_name}, Row {index + 1}: " + ", ".join([f"{col}: {val}" for col, val in row.items()])
            documents.append({
                "text": row_text,
                "metadata": {"sheet": sheet_name, "row": index + 1}
            })
    return documents
