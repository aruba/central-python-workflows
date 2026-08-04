import csv
import os


def write_csv(folder, filename, rows):
    """Write rows (list of dicts) to folder/filename. Creates folder if needed. rows must be non-empty."""
    os.makedirs(folder, exist_ok=True)
    fpath = os.path.join(folder, filename)
    with open(fpath, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return fpath
