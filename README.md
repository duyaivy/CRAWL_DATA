# Fashion Data Pipeline

Category-by-category pipeline for crawling fashion product metadata, validating image URLs, reviewing results, uploading approved images to Cloudinary, and building MongoDB-ready CSV data.

## Folder Flow

- `data/raw/{category}_raw.csv`
- `data/validated/{category}_validated.csv`
- `data/clean/{category}_clean.csv`
- `data/cloudinary/{category}_cloudinary.csv`
- `data/final/{category}_data.csv`

The scripts create these folders automatically.

## Run One Category

```powershell
python scripts/01_crawl.py --category vay --target 1000 --keyword "vay"
python scripts/02_validate.py --category vay
python scripts/03_human_validate_server.py --category vay
python scripts/04_upload_cloudinary.py --category vay
python scripts/05_build_mongo_data.py --category vay
python scripts/06_import_mongodb.py --category vay
```

You can also use `main.py`:

```powershell
python main.py crawl --category vay --target 1000 --keyword "vay"
python main.py validate --category vay
python main.py human-validate --category vay
python main.py upload --category vay
python main.py build-final --category vay
python main.py import-db --category vay
```

## Pipeline Steps

1. Crawl raw metadata with the existing Lazada Selenium crawler. Output: `data/raw/{category}_raw.csv`.
2. Validate required fields and image URLs from `original_image_url`. Output: `data/validated/{category}_validated.csv`.
3. Review accepted auto-validation rows in the local Streamlit server. Output: `data/clean/{category}_clean.csv`.
4. Upload clean image URLs to Cloudinary. Output mapping: `data/cloudinary/{category}_cloudinary.csv`.
5. Build final MongoDB CSV. Output: `data/final/{category}_data.csv`.
6. Optionally import final CSV rows into MongoDB.

## Cloudinary Env

Copy `.env.example` to `.env` and set:

```text
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
```

The Cloudinary mapping CSV contains exactly:

```text
filename,secure_url,public_id
```

The clean product CSV is also updated after upload with:

```text
cloudinary_url,cloudinary_public_id,uploaded_at,filename
```

## Final CSV Columns

`data/final/{category}_data.csv` contains:

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
