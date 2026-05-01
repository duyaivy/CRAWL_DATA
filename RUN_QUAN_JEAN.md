# Chay thu pipeline cho `quan_jean`

Muc tieu hien tai: crawl thu `quan_jean` truoc, moi lan lay 1 san pham. Category, keyword, target duoc sua trong code tai:

```text
src/config.py
```

Config hien tai:

```python
CATEGORIES = {
    "quan_jean": ["quan jean"],
}

DEFAULT_CATEGORY = "quan_jean"
TARGET_PER_CATEGORY = 1
MAX_PAGES_PER_CATEGORY = 10
```

Khi muon doi category/keyword/so luong, sua `src/config.py` truoc, sau do chay lai cac lenh ben duoi. Khong can truyen `--category`, `--target`, `--keyword` tu command line nua.

## 0. Kiem tra moi truong

Chay trong thu muc root cua project:

```powershell
cd D:\QUOCDUY\KHDL\CRAWLDATAA
```

Neu virtualenv dung duoc:

```powershell
.\venv\Scripts\Activate.ps1
python --version
```

Neu `python` khong nhan, sua lai Python/venv truoc khi chay pipeline.

## 1. Crawl 1 san pham quan jean

```powershell
python main.py crawl
```

Crawler se dung URL search dang:

```text
https://www.lazada.vn/tag/qu%E1%BA%A7n-jean/?spm=a2o4n.homepage.search.d_go&q=qu%E1%BA%A7n%20jean&catalog_redirect_tag=true
```

Output mong doi:

```text
data/raw/quan_jean_raw.csv
```

Kiem tra nhanh file raw:

```powershell
Get-Content data\raw\quan_jean_raw.csv -TotalCount 5
```

## 2. Validate tu dong

```powershell
python main.py validate
```

Output mong doi:

```text
data/validated/quan_jean_validated.csv
```

Kiem tra nhanh:

```powershell
Get-Content data\validated\quan_jean_validated.csv -TotalCount 5
```

Neu file validated chi co header hoac rong, san pham dau tien co the bi reject do anh loi, anh nho, anh mo, hoac duplicate. Khi do tang `TARGET_PER_CATEGORY` trong `src/config.py` len `5`, roi chay lai:

```powershell
python main.py crawl
python main.py validate
```

## 3. Human validate bang web local

```powershell
python main.py human-validate
```

Trong web:

- Xem anh, ten, gia, brand, source.
- De nguyen category neu dung.
- Tick reject neu san pham khong dung.
- Bam `Save Page`.
- Bam `Export Clean CSV`.

Output mong doi:

```text
data/clean/quan_jean_clean.csv
```

## 4. Upload anh len Cloudinary

Truoc khi chay, dam bao `.env` co:

```text
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

Chay upload:

```powershell
python -m src.upload_cloudinary
```

Mac dinh upload dung 8 luong. Neu muon chi ro:

```powershell
python -m src.upload_cloudinary --workers 8
```

Anh se duoc upload vao folder theo category. Voi flow hien tai, Cloudinary public id se co dang:

```text
quan_jean/10000
quan_jean/10001
quan_jean/10002
```

Khi chay, terminal se log tung anh:

```text
[1/67] Uploading: id=000001 filename=10000.jpg folder=quan_jean public_id=quan_jean/10000 ...
[1/67] Uploaded: id=000001 filename=10000.jpg public_id=quan_jean/10000 secure_url=...
```

Neu `data/clean/quan_jean_clean.csv` chua ton tai, uploader se tu lay cac dong `approved` trong:

```text
data/clean/quan_jean_reviewed.csv
```

roi tao file clean truoc khi upload.

Output mong doi:

```text
data/cloudinary/quan_jean_cloudinary.csv
data/clean/quan_jean_clean.csv
```

File Cloudinary mapping phai co format:

```text
filename,secure_url,public_id
```

## 5. Build CSV cuoi cho MongoDB

```powershell
python -m src.build_mongo
```

Output mong doi:

```text
data/final/quan_jean_data.csv
```

Kiem tra nhanh:

```powershell
Get-Content data\final\quan_jean_data.csv -TotalCount 5
```

## 6. Import MongoDB

Buoc nay optional. Chi chay khi `.env` da co:

```text
MONGODB_URI=
MONGODB_DATABASE=fashion_dataset
```

Chay import:

```powershell
python -m src.import_mongo
```

## Flow ngan gon

```powershell
python main.py crawl
python main.py validate
python main.py human-validate
python -m src.upload_cloudinary
python -m src.build_mongo
python -m src.import_mongo
```
