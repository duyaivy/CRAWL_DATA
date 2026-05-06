# OVERVIEW

Tài liệu này dùng để bàn giao source và hỗ trợ viết báo cáo về pipeline thu thập dữ liệu ảnh thời trang. Nội dung tập trung vào: mục tiêu pipeline, luồng xử lý tổng quan, khác biệt kỹ thuật crawl giữa Lazada/Tiki/ASOS, bước validate đang kiểm tra những gì, và cách chạy lại pipeline cho một category mới.

## 1. Tổng Quan Hệ Thống

Pipeline tạo dataset theo từng `category`. Mỗi category có một hoặc nhiều keyword search, được cấu hình trong:

```text
src/config.py
```

Ví dụ cấu hình hiện tại:

```python
CATEGORIES: dict[str, list[str]] = {"vay": ["maxi dress"]}
DEFAULT_CATEGORY: str = "vay"
TARGET_PER_CATEGORY: int = 300
MAX_PAGES_PER_CATEGORY: int = 100
CRAWLER_SOURCE: str = "asos"
```

Ý nghĩa:

- `CATEGORIES`: map category nội bộ sang danh sách keyword dùng để search.
- `DEFAULT_CATEGORY`: category mặc định khi chạy command không override.
- `TARGET_PER_CATEGORY`: số dòng ảnh/sản phẩm mục tiêu cần thu thập cho category.
- `MAX_PAGES_PER_CATEGORY`: số page tối đa crawler được phép quét.
- `CRAWLER_SOURCE`: marketplace đang crawl, gồm `lazada`, `tiki`, hoặc `asos`.

Pipeline gồm 6 giai đoạn chính:

1. Crawl metadata sản phẩm và URL ảnh từ marketplace.
2. Auto validate dữ liệu và ảnh.
3. Human validate bằng giao diện Streamlit local.
4. Upload ảnh đã duyệt lên Cloudinary.
5. Build CSV cuối theo schema để import MongoDB.
6. Import MongoDB, nếu cần.

Đầu ra được tách theo category:

```text
data/raw/{category}_raw.csv
data/validated/{category}_validated.csv
data/clean/{category}_reviewed.csv
data/clean/{category}_clean.csv
data/cloudinary/{category}_cloudinary.csv
data/final/{category}_data.csv
```

## 2. File Quan Trọng

- `main.py`: CLI chính để chạy từng bước pipeline.
- `src/config.py`: cấu hình category, keyword, source crawler, target, path, validation threshold.
- `src/crawler.py`: entrypoint crawl, dispatch sang crawler theo `CRAWLER_SOURCE`.
- `src/crawler_lazada.py`: crawl Lazada bằng Selenium và DOM/JSON-LD fallback.
- `src/crawler_tiki.py`: crawl Tiki bằng API JSON.
- `src/crawler_asos.py`: crawl ASOS bằng API JSON.
- `src/validator.py`: auto validate field, download ảnh, kích thước, blur, duplicate.
- `src/reviewer_app.py`: Streamlit app để human validate.
- `src/uploader.py`: upload ảnh lên Cloudinary.
- `src/final_builder.py`: build final CSV theo schema MongoDB.
- `src/db_importer.py`: import final CSV vào MongoDB.

## 3. Kỹ Thuật Crawl Theo Từng Source

Ba marketplace không crawl giống nhau vì cách render và API khác nhau.

### Lazada

Lazada dùng Selenium vì kết quả search render trên web và ảnh có lazy-load. Crawler mở Chrome, vào URL tag/search, scroll để product card và image load đầy đủ, sau đó trích xuất từ DOM.

Kỹ thuật chính:

- Build URL dạng `https://www.lazada.vn/tag/{keyword-slug}/?...&q={keyword}`.
- Dùng selector product card `div[data-qa-locator="product-item"]`.
- Lấy name/link từ `.RfADt a`, price từ `.ooOxS`, ảnh từ các attribute `src`, `data-src`, `data-ks-lazyload`, hoặc `srcset`.
- Normalize URL ảnh, bỏ suffix resize phổ biến của Lazada như `.jpg_200x200q80.jpg`.
- Nếu DOM extraction rỗng thì fallback đọc `script[type="application/ld+json"]`.
- Có `--skip-pages` để bỏ qua các page đầu khi cần crawl bổ sung.

Lazada chậm và dễ thay đổi selector hơn Tiki/ASOS, nhưng cần Selenium để xử lý render/lazy-load.

### Tiki

Tiki crawl trực tiếp qua API JSON `https://tiki.vn/api/v2/products`, nên không cần Selenium.

Kỹ thuật chính:

- Gửi request bằng `requests.Session`.
- Params gồm `limit`, `q`, `page`, `include=advertisement`, `is_mweb=1`, `aggregations=2`, `trackity_id`.
- Header giả lập browser gồm `User-Agent`, `Referer`, `Accept`.
- Đọc list product từ field JSON `data`.
- Lấy `name`, `price`, `brand_name`, `url_path`, `thumbnail_url`.
- Normalize ảnh bằng cách đổi URL cache `salt.tikicdn.com/cache/280x280/` về URL gốc hơn `salt.tikicdn.com/`.
- Delay giữa các request bằng `REQUEST_DELAY` để tránh spam.

Tiki nhanh và ổn định hơn vì dùng API, nhưng phụ thuộc response shape và `trackity_id`.

### ASOS

ASOS cũng crawl bằng API JSON `https://www.asos.com/api/product/search/v2/`.

Kỹ thuật chính:

- Gửi request theo `offset`, `q`, `store=ROW`, `lang=en-GB`, `currency=USD`, `limit`, `country=VN`.
- Mỗi page dùng offset: `offset = page * LIMIT`.
- Đọc product từ JSON field `products`.
- Build product URL từ `https://www.asos.com/` + `url`.
- Lấy price từ `price.current.value`, brand từ `brandName`.
- Chọn tối đa 2 ảnh cho mỗi product: primary `imageUrl` trước, sau đó ảnh số 3 trong `additionalImageUrls` là `additionalImageUrls[2]`.
- Normalize URL ảnh bằng cách thêm `https://` và `.jpg` nếu cần.

ASOS phù hợp để lấy ảnh người mẫu/quần áo theo keyword tiếng Anh. Một product có thể sinh nhiều dòng vì lấy nhiều ảnh của cùng sản phẩm.

## 4. Validate Là Validate Cái Gì?

Bước validate tự động nằm trong `src/validator.py`, output là:

```text
data/validated/{category}_validated.csv
```

Validator không chỉ kiểm tra CSV có dòng hay không. Nó lọc những dòng không đạt yêu cầu để ảnh đưa vào human review sạch hơn.

Validator kiểm tra:

- Field bắt buộc: `name`, `source`, `source_url`, `category`.
- Ảnh có URL hợp lệ trong `original_image_url` hoặc field image tương đương.
- Ảnh download được trong timeout.
- File download mở được bằng PIL, không bị lỗi format.
- Kích thước ảnh đạt tối thiểu `MIN_WIDTH` x `MIN_HEIGHT` trong `src/config.py`, hiện tại là `300 x 300`.
- Độ nét ảnh bằng variance of Laplacian; nếu `blur_score < BLUR_THRESHOLD` thì reject, hiện tại threshold là `40.0`.
- Trùng source/image URL trong cùng batch.
- Trùng ảnh gần đúng bằng perceptual hash; nếu khoảng cách hash <= `HASH_DISTANCE_THRESHOLD` thì reject, hiện tại threshold là `5`.

Những lý do reject thường gặp:

```text
missing_name
missing_image_url
duplicate_url
download_failed
invalid_image_format
too_small
too_blurry
duplicate_image
```

Nếu muốn bỏ qua validate ảnh để test nhanh, có thể chạy:

```powershell
python main.py validate --auto-pass-all
```

Chế độ này chỉ nên dùng để debug flow, không nên dùng cho dataset cuối.

## 5. Flow Chạy Pipeline

Chuẩn bị terminal tại root project:

```powershell
cd D:\QUOCDUY\KHDL\CRAWLDATAA
.\venv\Scripts\Activate.ps1
python --version
```

Nếu `python` không nhận hoặc version quá cũ, cần sửa Python/venv trước.

### Bước 1: Crawl

Sửa `src/config.py` trước khi crawl:

```python
CATEGORIES = {"vay": ["maxi dress"]}
DEFAULT_CATEGORY = "vay"
TARGET_PER_CATEGORY = 300
MAX_PAGES_PER_CATEGORY = 100
CRAWLER_SOURCE = "asos"
```

Chạy:

```powershell
python main.py crawl
```

Output:

```text
data/raw/{category}_raw.csv
```

Kiểm tra nhanh:

```powershell
Get-Content data\raw\vay_raw.csv -TotalCount 5
```

### Bước 2: Auto Validate

```powershell
python main.py validate
```

Output:

```text
data/validated/{category}_validated.csv
```

Nếu output chỉ có header hoặc quá ít dòng, lý do thường là ảnh lỗi, ảnh nhỏ, ảnh mờ, duplicate, hoặc marketplace trả URL không download được. Có thể tăng `TARGET_PER_CATEGORY`, đổi keyword, hoặc tạm dùng `--auto-pass-all` để debug.

### Bước 3: Human Validate

```powershell
python main.py human-validate
```

Trong web local:

- Xem ảnh, tên sản phẩm, giá, brand, source.
- Sửa `final_category` nếu sản phẩm cần gán lại nhãn.
- Reject sản phẩm sai category, ảnh xấu, ảnh duplicate, ảnh không phù hợp.
- Bấm `Save Page`.
- Bấm `Export Clean CSV`.

Output:

```text
data/clean/{category}_reviewed.csv
data/clean/{category}_clean.csv
```

### Bước 4: Upload Cloudinary

Cần cấu hình `.env`:

```text
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

Chạy:

```powershell
python main.py upload
```

Hoặc dùng wrapper có số worker:

```powershell
python -m src.upload_cloudinary --workers 8
```

Output:

```text
data/cloudinary/{category}_cloudinary.csv
```

Cloudinary public id nằm theo folder category, ví dụ:

```text
vay/10000
vay/10001
vay/10002
```

### Bước 5: Build Final CSV

```powershell
python main.py build-final
```

Output:

```text
data/final/{category}_data.csv
```

Final CSV gồm các field chính:

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

### Bước 6: Import MongoDB

Bước này optional. Cần thêm `.env`:

```text
MONGODB_URI=
MONGODB_DATABASE=fashion_dataset
```

Chạy:

```powershell
python main.py import-db
```

## 6. Lệnh Chạy Nhanh

Sau khi sửa `src/config.py`, chạy lần lượt:

```powershell
python main.py crawl
python main.py validate
python main.py human-validate
python main.py upload
python main.py build-final
python main.py import-db
```

Nếu chưa cần MongoDB, dừng tại:

```powershell
python main.py build-final
```

Có thể override tạm thời khi test:

```powershell
python main.py crawl --category vay --target 20 --keyword "maxi dress" --max-pages 2
```

Với Lazada, có thêm:

```powershell
python main.py crawl --category quan_jean --keyword "quan jean" --skip-pages 3
```

Khi bàn giao hoặc viết báo cáo, nên ghi rõ config trong `src/config.py` thay vì chỉ ghi command override, để người khác lặp lại đúng cùng điều kiện.

## 7. Gợi Ý Viết Báo Cáo

Có thể mô tả pipeline theo các ý sau:

- Mục tiêu: thu thập dataset ảnh thời trang theo category, gồm metadata sản phẩm, URL gốc, URL Cloudinary và nhãn cuối.
- Nguồn dữ liệu: Lazada, Tiki, ASOS; mỗi source có kỹ thuật crawl riêng do cách cung cấp dữ liệu khác nhau.
- Tiền xử lý: normalize URL, loại duplicate theo URL, chuẩn hóa schema raw CSV.
- Kiểm định chất lượng: auto validate field, download ảnh, kích thước, độ mờ, duplicate perceptual hash.
- Kiểm định thủ công: human review để loại sản phẩm sai nhãn hoặc ảnh không đúng.
- Lưu trữ: upload ảnh lên Cloudinary và build CSV theo schema MongoDB.
