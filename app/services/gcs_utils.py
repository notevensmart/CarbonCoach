from google.cloud import storage
import os

def download_files(file_specs, target_dir):
    client = storage.Client()
    os.makedirs(target_dir, exist_ok=True)

    for bucket_name, source_blob_name in file_specs:
        dest_path = os.path.join(target_dir, os.path.basename(source_blob_name))
        if not os.path.exists(dest_path):
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(source_blob_name)
            blob.download_to_filename(dest_path)
            print(f"Downloaded {source_blob_name} to {dest_path}")
            
