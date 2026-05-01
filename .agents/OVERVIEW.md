You are working on an existing fashion data crawling/validation/upload project.

Please inspect the current codebase first, then update the existing flow. Do not rewrite everything from scratch unless necessary. Reuse the current crawler, validator, human validation server, and upload scripts as much as possible.

# Goal

Refactor the current project into a clear data pipeline:

1. Auto crawl enough products for each category/keyword.
2. Run automatic validation.
3. Run human validation using a local web server.
4. Upload images from image URLs to Cloudinary.
5. Build final CSV files that can be used for MongoDB import.

# New Pipeline

## Step 1: Auto Crawl

Use the current crawler code.

The crawler should automatically collect enough products based on:
- category
- keyword
- target amount

Each category may have its own keyword list.

Expected output:

```
data/raw/{category}_raw.csv
```

Example:

```
data/raw/vay_raw.csv
data/raw/ao_thun_raw.csv
```

The raw CSV should keep important fields such as:

```
name
price
brand
source
source_url
original_image_url
category
final_category
```

If `final_category` does not exist at this step, create it from the current category.

## Step 2: Automatic Validation

Create or update the validation script to read from:

```
data/raw/{category}_raw.csv
```

The validator should check records and images from `original_image_url`.

Validation rules should remove records with:
- missing image URL
- image URL cannot be downloaded
- invalid image format
- image too small
- missing important fields
- duplicate products if duplicate detection already exists

Images do not need to be stored permanently during validation. They can be downloaded temporarily into memory or a temp folder.

Expected output:

```
data/validated/{category}_validated.csv
```

## Step 3: Human Validation Web Server

Create or update the human validation web server.

The server should read from:

```
data/validated/{category}_validated.csv
```

The web UI should display product information:

```
image
name
price
brand
source
source_url
original_image_url
category
final_category
```

Required actions:
- Accept / Keep
- Reject
- Update category if needed

After human validation is completed, save the clean result to:

```
data/clean/{category}_clean.csv
```

## Step 4: Upload Images to Cloudinary

Create or update the Cloudinary upload script.

The script should read from:

```
data/clean/{category}_clean.csv
```

It should upload images from `original_image_url` to Cloudinary.

Upload images into a Cloudinary folder based on category.

Example Cloudinary public IDs:

```
vay/10000
vay/10001
ao_thun/10002
```

Example filenames:

```
10000.jpg
10001.jpg
10002.jpg
```

After uploading, create a Cloudinary mapping CSV:

```
data/cloudinary/{category}_cloudinary.csv
```

The Cloudinary mapping CSV must follow this exact format:

```
filename,secure_url,public_id
10000.jpg,https://res.cloudinary.com/dtadw36tk/image/upload/v1777571373/vay/10000.jpg,vay/10000
10001.jpg,https://res.cloudinary.com/dtadw36tk/image/upload/v1777571373/vay/10001.jpg,vay/10001
```

Also make sure the clean product data can be updated with these fields:

```
cloudinary_url
cloudinary_public_id
uploaded_at
filename
```

## Step 5: Build Final MongoDB CSV Data

After Cloudinary upload is completed, merge:

```
data/clean/{category}_clean.csv
```

with:

```
data/cloudinary/{category}_cloudinary.csv
```

Then generate the final data file:

```
data/final/{category}_data.csv
```

This file must match the MongoDB schema below:

````python
return {
    "category": row.get("final_category", ""),
    "name": row.get("name", ""),
    "price": row.get("price", ""),
    "brand": row.get("brand", ""),
    "source": row.get("source", ""),
    "sourceUrl": row.get("source_url", ""),
    "originalImageUrl": row.get("original_image_url", ""),
    "cloudinaryUrl": row.get("cloudinary_url", ""),
    "cloudinaryPublicId": row.get("cloudinary_public_id", ""),
    "createdAt": row.get("uploaded_at", ""),
}

The final CSV should contain these columns:

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

At this stage, importing into MongoDB is optional. The main goal is to generate a clean `{category}_data.csv` file that is ready for MongoDB import.

If a MongoDB import script already exists, update it to read from:

data/final/{category}_data.csv

If it does not exist, you may create a separate script:

scripts/06_import_mongodb.py

# Suggested Script Structure

If the project already has similar scripts, update them instead of creating duplicates.

Preferred structure:

scripts/01_crawl.py
scripts/02_validate.py
scripts/03_human_validate_server.py
scripts/04_upload_cloudinary.py
scripts/05_build_mongo_data.py
scripts/06_import_mongodb.py

Each script should be runnable independently from CLI.

Example commands:

python scripts/01_crawl.py --category vay --target 1000
python scripts/02_validate.py --category vay
python scripts/03_human_validate_server.py --category vay
python scripts/04_upload_cloudinary.py --category vay
python scripts/05_build_mongo_data.py --category vay
python scripts/06_import_mongodb.py --category vay

# Required Folder Structure

Please make sure the pipeline creates and uses these folders:

data/raw/
data/validated/
data/clean/
data/cloudinary/
data/final/

Expected files after running the full pipeline:

data/raw/{category}_raw.csv
data/validated/{category}_validated.csv
data/clean/{category}_clean.csv
data/cloudinary/{category}_cloudinary.csv
data/final/{category}_data.csv

# Cloudinary Requirements

Do not hardcode Cloudinary secrets.

Read Cloudinary config from `.env`.

Expected environment variables:

CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

The upload script should save at least:

filename
secure_url
public_id
uploaded_at

The mapping CSV must contain this exact minimum format:

filename,secure_url,public_id

# Important Implementation Requirements

Before modifying code:

1. Inspect the current codebase.
2. Identify files related to:
   - crawling
   - automatic validation
   - human validation server
   - Cloudinary upload
   - final CSV building
   - MongoDB import
3. Explain which files need to be changed.
4. Then apply the changes.

Do not break existing working code unless required by the new pipeline.

Prefer small, clear refactors over large rewrites.

Each step must have:

- clear input file
- clear output file
- clear CLI command
- clear error handling
- clear logs

# Definition of Done

The task is complete when:

- The full pipeline can run category by category.
- Each step can run independently.
- Each step reads input from the previous step.
- Each step writes output to the correct folder.
- The crawler can crawl enough products based on category/keyword/target amount.
- Automatic validation outputs `{category}_validated.csv`.
- Human validation web server outputs `{category}_clean.csv`.
- Cloudinary upload outputs `{category}_cloudinary.csv`.
- Cloudinary mapping CSV has this format:
  filename,secure_url,public_id
- Final MongoDB-ready CSV is generated at:
  data/final/{category}_data.csv
- Final CSV contains:
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
- A short README section is added or updated to explain how to run the pipeline.
- A `FLOW_UPDATE.md` file is added or updated after each completed part.

# FLOW_UPDATE.md Requirement

After finishing each part, update:

FLOW_UPDATE.md

It should include:

## Updated Part
What was changed?

## Changed Files
List changed files.

## How To Test
Commands to run.

## Expected Output
Files or results expected after testing.

## Notes
Any important implementation notes.

# Final Note

This is a flow refactor task, not a brand-new project.

Focus on making the existing codebase follow the new pipeline clearly and safely.