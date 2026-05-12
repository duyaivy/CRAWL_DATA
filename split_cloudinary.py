"""
split_cloudinary.py
-------------------
Đọc tất cả file CSV trong thư mục cloudinary_links,
phân chia mỗi file theo tỉ lệ train 80% / valid 10% / test 10%,
lưu kết quả vào cloudinary_links/train/, valid/, test/.
"""

import os
import math
import random
import csv

# ── Cấu hình ──────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.join(os.path.dirname(__file__), "cloudinary_links")
SPLITS        = {"train": 0.8, "valid": 0.1, "test": 0.1}
RANDOM_SEED   = 42          # đặt seed để kết quả tái lập được
# ──────────────────────────────────────────────────────────────────────────────


def split_csv(filepath: str, out_dirs: dict[str, str]) -> dict[str, int]:
    """Đọc CSV, shuffle, chia theo tỉ lệ, ghi ra 3 thư mục."""
    filename = os.path.basename(filepath)

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows   = list(reader)

    random.shuffle(rows)
    n = len(rows)

    n_train = math.floor(n * SPLITS["train"])
    n_valid = math.floor(n * SPLITS["valid"])
    # test nhận phần còn lại để tổng = n
    n_test  = n - n_train - n_valid

    chunks = {
        "train": rows[:n_train],
        "valid": rows[n_train : n_train + n_valid],
        "test" : rows[n_train + n_valid :],
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

    # Tạo thư mục train / valid / test
    out_dirs = {}
    for split in SPLITS:
        path = os.path.join(BASE_DIR, split)
        os.makedirs(path, exist_ok=True)
        out_dirs[split] = path

    # Lấy danh sách CSV trong thư mục gốc (không đệ quy)
    csv_files = sorted(
        os.path.join(BASE_DIR, f)
        for f in os.listdir(BASE_DIR)
        if f.endswith(".csv") and os.path.isfile(os.path.join(BASE_DIR, f))
    )

    if not csv_files:
        print("Không tìm thấy file CSV nào trong", BASE_DIR)
        return

    print(f"Tìm thấy {len(csv_files)} file CSV\n")
    print(f"{'File':<30} {'Total':>7} {'Train':>7} {'Valid':>7} {'Test':>7}")
    print("-" * 60)

    for filepath in csv_files:
        counts = split_csv(filepath, out_dirs)
        total  = sum(counts.values())
        name   = os.path.basename(filepath)
        print(
            f"{name:<30} {total:>7} "
            f"{counts['train']:>7} {counts['valid']:>7} {counts['test']:>7}"
        )

    print("\nHoàn thành! Kết quả lưu tại:")
    for split, path in out_dirs.items():
        print(f"  {split:6s} → {path}")


if __name__ == "__main__":
    main()
