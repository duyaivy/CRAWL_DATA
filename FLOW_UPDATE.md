# FLOW_UPDATE

## Updated Part

Da chinh lai flow crawl/upload cho giai doan test `quan_jean`:

- Category/keyword/target lay tu `src/config.py`, khong can truyen tu command line.
- `TARGET_PER_CATEGORY` hien tai la `1` de crawl thu tung san pham.
- Upload Cloudinary mac dinh chay 8 luong.
- Upload Cloudinary dung folder theo category, vi du `quan_jean/10000`.
- Upload Cloudinary log tung anh khi bat dau upload, upload thanh cong, skip, hoac fail.
- Neu `data/clean/quan_jean_clean.csv` chua co, uploader tu tao clean CSV tu cac dong `approved` trong `data/clean/quan_jean_reviewed.csv`.
- URL Lazada search da doi sang format dang chay duoc:

```text
https://www.lazada.vn/tag/qu%E1%BA%A7n-jean/?spm=a2o4n.homepage.search.d_go&q=qu%E1%BA%A7n%20jean&catalog_redirect_tag=true
```

Voi page sau crawler se them `&page=2`, `&page=3`, ...

## Changed Files

- `src/config.py`
- `src/crawler_lazada.py`
- `main.py`
- `src/uploader.py`
- `src/upload_cloudinary.py`
- `RUN_QUAN_JEAN.md`
- `FLOW_UPDATE.md`

## How To Test

Chay tung buoc, khong can truyen category/target/keyword:

```powershell
python main.py crawl
python main.py validate
python main.py human-validate
python -m src.upload_cloudinary --workers 8
python -m src.build_mongo
python -m src.import_monggo
```

Neu muon crawl nhieu hon, sua trong `src/config.py`:

```python
TARGET_PER_CATEGORY = 5
```

roi chay lai:

```powershell
python main.py crawl
```

## Expected Output

- `data/raw/quan_jean_raw.csv`
- `data/validated/quan_jean_validated.csv`
- `data/clean/quan_jean_clean.csv`
- `data/cloudinary/quan_jean_cloudinary.csv`
- `data/final/quan_jean_data.csv`

## Notes

- Huong dan day du nam trong `RUN_QUAN_JEAN.md`.
- Category hien tai la `quan_jean`, keyword la `quan jean`.
- Khi can doi category, sua `CATEGORIES` va `DEFAULT_CATEGORY` trong `src/config.py`.
