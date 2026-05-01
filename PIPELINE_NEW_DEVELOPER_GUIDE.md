# Huong Dan Flow Crawl Va Tao Data Moi

File nay danh cho nguoi moi nhan source de hieu flow, biet sua tham so o dau, va biet chay lenh nao de crawl mot loai san pham khac.

## 1. Y Tuong Chinh

Pipeline hien tai chay theo tung category. Category, keyword, target crawl duoc cau hinh trong:

```text
src/config.py
```

Nguoi chay pipeline khong can truyen category/keyword/target bang command line trong flow binh thuong. Sua config truoc, sau do chay cac lenh.

Flow gom 6 buoc:

1. Crawl san pham tu Lazada.
2. Validate tu dong anh va field bat buoc.
3. Human validate bang web local.
4. Upload anh len Cloudinary theo folder category.
5. Build CSV cuoi dung schema MongoDB.
6. Import MongoDB, optional.

## 2. File Quan Trong

- `src/config.py`: sua category, keyword, target, folder path, validation setting.
- `src/crawler.py`: entrypoint crawler.
- `src/crawler_lazada.py`: logic crawl Lazada.
- `src/validator.py`: validate image URL va metadata.
- `src/reviewer_app.py`: Streamlit app de review thu cong.
- `src/uploader.py`: upload image len Cloudinary, mac dinh 8 luong.
- `src/upload_cloudinary.py`: CLI wrapper cho upload.
- `src/final_builder.py`: tao CSV cuoi cho MongoDB.
- `src/build_mongo.py`: CLI wrapper build Mongo CSV.
- `src/db_importer.py`: import final CSV vao MongoDB.
- `src/import_mongo.py`: CLI wrapper import MongoDB.

## 3. Sua Category, Keyword, Target

Mo file:

```text
src/config.py
```

Vi du hien tai:

```python
CATEGORIES: dict[str, list[str]] = {
    "quan_jean": ["quan jean"],
}

DEFAULT_CATEGORY: str = "quan_jean"
TARGET_PER_CATEGORY: int = 600
MAX_PAGES_PER_CATEGORY: int = 100
```

Y nghia:

- `CATEGORIES`: map category noi bo sang danh sach keyword search Lazada.
- `DEFAULT_CATEGORY`: category mac dinh khi chay lenh khong truyen `--category`.
- `TARGET_PER_CATEGORY`: so san pham can crawl cho category hien tai.
- `MAX_PAGES_PER_CATEGORY`: so page Lazada toi da crawler duoc phep quet.

## 4. Vi Du Doi Sang San Pham Khac

Neu muon crawl `ao_thun`, sua `src/config.py` thanh:

```python
CATEGORIES: dict[str, list[str]] = {
    "ao_thun": ["ao thun", "áo thun"],
}

DEFAULT_CATEGORY: str = "ao_thun"
TARGET_PER_CATEGORY: int = 100
MAX_PAGES_PER_CATEGORY: int = 50
```

Output se tu doi theo category:

```text
data/raw/ao_thun_raw.csv
data/validated/ao_thun_validated.csv
data/clean/ao_thun_reviewed.csv
data/clean/ao_thun_clean.csv
data/cloudinary/ao_thun_cloudinary.csv
data/final/ao_thun_data.csv
```

Cloudinary public id se nam trong folder category:

```text
ao_thun/10000
ao_thun/10001
ao_thun/10002
```

## 5. Chuan Bi Moi Truong

Dung terminal tai root project:

```powershell
cd D:\QUOCDUY\KHDL\CRAWLDATAA
```

Kich hoat virtualenv neu dung PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
python --version
```

Neu `python` khong nhan hoac venv loi, can sua Python/venv truoc.

## 6. Cau Hinh `.env`

Cloudinary upload can:

```text
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

MongoDB import la optional. Neu can import MongoDB thi them:

```text
MONGODB_URI=
MONGODB_DATABASE=fashion_dataset
```

Khong commit `.env` len git.

## 7. Chay Tung Buoc

### Buoc 1: Crawl

```powershell
python main.py crawl
```

Output:

```text
data/raw/{category}_raw.csv
```

Vi du voi `quan_jean`:

```text
data/raw/quan_jean_raw.csv
```

Kiem tra nhanh:

```powershell
Get-Content data\raw\quan_jean_raw.csv -TotalCount 5
```

### Buoc 2: Validate Tu Dong

```powershell
python main.py validate
```

Output:

```text
data/validated/{category}_validated.csv
```

Vi du:

```powershell
Get-Content data\validated\quan_jean_validated.csv -TotalCount 5
```

Neu file chi co header hoac rong, co the do anh loi, anh nho, anh mo, duplicate, hoac khong download duoc. Tang `TARGET_PER_CATEGORY` trong `src/config.py` roi crawl lai.

### Buoc 3: Human Validate

```powershell
python main.py human-validate
```

Trong web:

- Xem anh, ten san pham, gia, brand, source.
- Doi `final_category` neu can.
- Tick reject neu san pham sai.
- Bam `Save Page`.
- Bam `Export Clean CSV`.

Output:

```text
data/clean/{category}_reviewed.csv
data/clean/{category}_clean.csv
```

Neu quen bam `Export Clean CSV`, buoc upload van co the tu tao clean CSV tu cac dong `approved` trong reviewed CSV.

### Buoc 4: Upload Cloudinary

```powershell
python -m src.upload_cloudinary --workers 8
```

Mac dinh uploader upload 8 luong. Moi anh se log tien trinh:

```text
[1/67] Uploading: id=000001 filename=10000.jpg folder=quan_jean public_id=quan_jean/10000 ...
[1/67] Uploaded: id=000001 filename=10000.jpg public_id=quan_jean/10000 secure_url=...
```

Output:

```text
data/cloudinary/{category}_cloudinary.csv
data/clean/{category}_clean.csv
```

Cloudinary mapping CSV co format:

```text
filename,secure_url,public_id
```

### Buoc 5: Build MongoDB CSV

```powershell
python -m src.build_mongo
```

Output:

```text
data/final/{category}_data.csv
```

Kiem tra nhanh:

```powershell
Get-Content data\final\quan_jean_data.csv -TotalCount 5
```

Final CSV columns:

```text
category
name
price
brand
source
sourceUrl
originalImageUrl
cloudinaryUrl
cloudinaryPublicId
createdAt
```

### Buoc 6: Import MongoDB

Buoc nay optional.

```powershell
python -m src.import_mongo
```

Hoac:

```powershell
python main.py import-db
```

## 8. Flow Ngan Gon

Sau khi da sua `src/config.py`, chay:

```powershell
python main.py crawl
python main.py validate
python main.py human-validate
python -m src.upload_cloudinary --workers 8
python -m src.build_mongo
python -m src.import_mongo
```

Neu chua muon import MongoDB, dung tai buoc:

```powershell
python -m src.build_mongo
```

## 9. Chay Tam Thoi Khac Config

Flow khuyen nghi la sua `src/config.py`. Tuy nhien `main.py` van ho tro override tam thoi:

```powershell
python main.py crawl --category quan_jean --target 10 --keyword "quan jean"
```

Chi dung cach nay khi test nhanh. Khi ban giao cho nguoi khac, nen sua config de flow ro rang va lap lai duoc.

## 10. Loi Thuong Gap

### Khong co clean CSV khi upload

Neu thay:

```text
No input rows found at data\clean\{category}_clean.csv
```

Kiem tra reviewed CSV co dong approved chua:

```powershell
Get-Content data\clean\quan_jean_reviewed.csv -TotalCount 5
```

Uploader se tu tao clean CSV neu reviewed CSV co `human_status=approved`.

### Cloudinary upload sai folder

Uploader dung `final_category`, neu khong co thi dung `category`, neu khong co nua thi dung `DEFAULT_CATEGORY`. Kiem tra CSV clean phai co category dung.

Expected public id:

```text
{category}/10000
```

Vi du:

```text
quan_jean/10000
```

### Validate rong

Nguyen nhan thuong gap:

- URL anh khong download duoc.
- Anh qua nho.
- Anh bi blur.
- San pham duplicate.
- Thieu field bat buoc.

Tang `TARGET_PER_CATEGORY`, crawl lai, roi validate lai.

