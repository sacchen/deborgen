# Phase A: Artifact Storage via S3 Presigned URLs

## Goal
Implement artifact storage so jobs can generate files (like CSVs, images, or model weights) and workers can upload them securely to cloud storage without the coordinator buffering the file contents.

## Strategy
1. **S3 Presigned URLs:** The coordinator generates temporary, cryptographically signed URLs that allow direct `PUT` access to an S3 bucket.
2. **Direct Upload:** Workers use these URLs to upload artifacts directly to S3 (e.g., AWS, Cloudflare R2, Backblaze B2).
3. **Record Keeping:** The coordinator stores the final artifact URLs in its SQLite database.

## Educational Notes: Why We Did This

### 1. The Coordinator Bandwidth Problem
In a centralized hub-and-spoke system, the central node (the coordinator) can easily become a network bottleneck. If 10 workers finish a deep learning run simultaneously and try to upload 1GB of results directly to the coordinator, a cheap $5/month Droplet will run out of RAM, disk space, and network throughput. It will likely drop HTTP connections, causing heartbeats to fail and jobs to be marked as "lost."

### 2. The Solution: Presigned URLs
To keep the coordinator small, we used **S3 Presigned URLs**. 
* The coordinator acts merely as a secure ticket agent.
* The worker asks: "I have a file named `artifacts.zip`, where can I put it?"
* The coordinator uses its secret cloud credentials (via `boto3`) to generate a temporary, cryptographically signed URL. 
* The worker uses this URL to do an HTTP `PUT` directly to the object storage (AWS S3, Cloudflare R2).
* **Result:** The heavy lifting (moving gigabytes of data) happens between the worker and the massive cloud provider. The coordinator only processes a few bytes of JSON.

### 3. Isolation via Temporary Directories
In the worker agent (`agent.py`), we switched to using Python's `tempfile.TemporaryDirectory`. 
Previously, a job could accidentally write to the user's home folder or leave behind messy intermediate files. By running every job inside a dedicated `tmp/` folder, we achieve two things:
1. **Cleanliness:** The user's machine stays clean.
2. **Deterministic Artifacts:** We know exactly what the job produced. Anything left inside the `tmp/` folder when the process exits is considered an "artifact", safely zipped up, and uploaded.
## Progress
- [x] Create notes file.
- [x] Add `boto3` dependency to the project.
- [x] Update coordinator (`app.py`):
    - [x] Add S3 configuration (endpoint, bucket, credentials).
    - [x] Implement `POST /jobs/{id}/artifacts/presign` to generate upload URLs.
    - [x] Implement `POST /jobs/{id}/artifacts` to record final artifact URLs in SQLite.
- [x] Update worker agent (`agent.py`):
    - [x] Run jobs in an isolated temporary directory.
    - [x] Zip the contents of the working directory after the job finishes.
    - [x] Request a presigned URL from the coordinator.
    - [x] Upload the zip file to S3.
    - [x] Notify the coordinator to record the artifact URL.
- [x] Update API documentation (`api.md`).
