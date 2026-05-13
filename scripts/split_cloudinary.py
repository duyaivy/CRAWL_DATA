"""Split Cloudinary CSV files into train/valid/test sets.

Reads all CSV files from cloudinary_links/total and writes matching CSV files to:
cloudinary_links/train, cloudinary_links/valid, and cloudinary_links/test.
"""

import csv
import math
import os
import random


PROJECT_DIR = os.path.dirname(os.path.dirname(__file__))
CLOUDINARY_DIR = os.path.join(PROJECT_DIR, "cloudinary_links")
BASE_DIR = os.path.join(CLOUDINARY_DIR, "total")
SPLITS = {"train": 0.8, "valid": 0.1, "test": 0.1}
RANDOM_SEED = 42


def split_csv(filepath: str, out_dirs: dict[str, str]) -> dict[str, int]:
    """Read one CSV, shuffle rows, split, and write to three output folders."""
    filename = os.path.basename(filepath)

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    random.shuffle(rows)
    n = len(rows)

    n_train = math.floor(n * SPLITS["train"])
    n_valid = math.floor(n * SPLITS["valid"])
    n_test = n - n_train - n_valid

    chunks = {
        "train": rows[:n_train],
        "valid": rows[n_train : n_train + n_valid],
        "test": rows[n_train + n_valid :],
    }

    counts = {}
    for split, chunk in chunks.items():
        out_path = os.path.join(out_dirs[split], filename)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(chunk)
        counts[split] = len(chunk)

    return counts


def main():
    random.seed(RANDOM_SEED)

    out_dirs = {}
    for split in SPLITS:
        path = os.path.join(CLOUDINARY_DIR, split)
        os.makedirs(path, exist_ok=True)
        out_dirs[split] = path

    csv_files = sorted(
        os.path.join(BASE_DIR, f)
        for f in os.listdir(BASE_DIR)
        if f.endswith(".csv") and os.path.isfile(os.path.join(BASE_DIR, f))
    )

    if not csv_files:
        print("No CSV files found in", BASE_DIR)
        return

    print(f"Found {len(csv_files)} CSV files\n")
    print(f"{'File':<30} {'Total':>7} {'Train':>7} {'Valid':>7} {'Test':>7}")
    print("-" * 60)

    for filepath in csv_files:
        counts = split_csv(filepath, out_dirs)
        total = sum(counts.values())
        name = os.path.basename(filepath)
        print(
            f"{name:<30} {total:>7} "
            f"{counts['train']:>7} {counts['valid']:>7} {counts['test']:>7}"
        )

    print("\nDone. Output saved to:")
    for split, path in out_dirs.items():
        print(f"  {split:6s} -> {path}")


if __name__ == "__main__":
    main()
