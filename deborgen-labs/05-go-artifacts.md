# Lab 05: Go Worker — Artifacts

## Concept

This lab has three parts that chain together: isolated execution, zip
creation, and direct S3 upload via presigned URL.

The key new concept is **`defer`**. In Go, `defer someFunc()` schedules
`someFunc` to run when the surrounding function returns — no matter how it
returns (normal return, error, panic). This is how Go handles cleanup.

```go
tmpDir, _ := os.MkdirTemp("", "job-*")
defer os.RemoveAll(tmpDir)  // always cleans up, even if we panic
```

Compare this to Python's `with tempfile.TemporaryDirectory() as job_work_dir:`
— same guarantee, different syntax.

## Task

Extend your Lab 04 worker to:

1. Run each job inside a temporary directory (`os.MkdirTemp`)
2. After the job exits, check if any files were written to that directory
3. If files exist: zip the directory, upload via presigned URL, record with
   coordinator
4. Clean up the temp dir and zip file regardless of success or failure

The artifact flow:
1. `POST /jobs/{id}/artifacts/presign` with `{"node_id": ..., "lease_token": ..., "filename": "artifacts.zip"}`
   → returns `{"upload_url": "...", "download_url": "..."}`
2. `PUT {upload_url}` with the zip file as the request body
3. `POST /jobs/{id}/artifacts` with `{"node_id": ..., "lease_token": ..., "url": "{download_url}"}`

## Acceptance criteria

With the Python coordinator and a real S3/R2/B2 bucket configured (or skip
to criteria 4 if you don't have one yet):

1. Submit a job that writes a file:
   `{"command": "bash -c 'echo result > output.txt'"}`
   After it runs, `GET /jobs/job_1` shows a URL in `artifact_urls`.

2. The URL is downloadable and the zip contains `output.txt` with the
   content `result`.

3. Submit a job that writes nothing (`{"command": "echo hello"}`). No
   presign request is made, `artifact_urls` is empty.

4. (Without S3) Submit a job that writes a file. The worker logs that it
   found artifacts and attempted the presign request. It logs the 500 error
   gracefully and still finishes the job successfully.

## Key Go packages to use

- `os` — `os.MkdirTemp`, `os.ReadDir`, `os.RemoveAll`
- `archive/zip` — create zip files
- `path/filepath` — `filepath.Walk` to recurse into directories
- `io` — `io.Copy` to stream file contents into the zip
- `net/http` — `http.NewRequest("PUT", uploadURL, file)` for the S3 upload

## Hints

<details>
<summary>Hint 1: Checking if the directory has files</summary>

```go
entries, err := os.ReadDir(tmpDir)
if err != nil || len(entries) == 0 {
    // no artifacts
}
```

`os.ReadDir` returns directory entries. If the slice is empty, no files
were written.
</details>

<details>
<summary>Hint 2: Creating a zip file</summary>

```go
zipFile, err := os.CreateTemp("", "artifacts-*.zip")
defer os.Remove(zipFile.Name())

w := zip.NewWriter(zipFile)
defer w.Close()

filepath.Walk(srcDir, func(path string, info fs.FileInfo, err error) error {
    if info.IsDir() {
        return nil
    }
    relPath, _ := filepath.Rel(srcDir, path)
    f, _ := w.Create(relPath)
    src, _ := os.Open(path)
    defer src.Close()
    io.Copy(f, src)
    return nil
})
```

This walks the directory and writes each file into the zip at its relative
path.
</details>

<details>
<summary>Hint 3: Uploading to S3 with a PUT request</summary>

The presigned URL is a direct S3 URL — no Authorization header, no JSON,
just the file as the request body:

```go
file, err := os.Open(zipPath)
defer file.Close()

stat, _ := file.Stat()
req, _ := http.NewRequest("PUT", uploadURL, file)
req.ContentLength = stat.Size()

client := &http.Client{Timeout: 5 * time.Minute}
resp, err := client.Do(req)
```

Setting `ContentLength` is important — some S3-compatible providers reject
uploads without it.
</details>

<details>
<summary>Hint 4: Error handling strategy</summary>

Artifact upload failure should not fail the job. The Python worker wraps
the whole artifact block in `try/except` and logs the error. Do the same
in Go: if any step of the artifact flow fails, log it and continue to
`finish_job` with whatever exit code the job actually produced.
</details>

## When you're done

Your Go worker now replicates the full Python worker feature set. Move to
Lab 06.
