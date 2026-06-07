from huggingface_hub import snapshot_download

print("Starting download of BAAI/bge-m3...")
try:
    path = snapshot_download(repo_id="BAAI/bge-m3")
    print(f"\nSuccess! Model downloaded to: {path}")
except Exception as e:
    print(f"\nError downloading model: {e}")