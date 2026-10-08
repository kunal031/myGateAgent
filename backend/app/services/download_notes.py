import os
import requests
from pathlib import Path

NOTES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "documents" / "Notes"
os.makedirs(NOTES_DIR, exist_ok=True)

NOTES_FILES = [
    ("1LzD3sR7ws7s49TcDF8r9-qQ_nk5FZx-x", "01_Discrete_Mathematics_Notes.pdf"),
    ("1gln5Mm4VR0bAIBfj2e28AWL6ccV0o6y5", "02_TOC_Theory_of_Computation_Notes.pdf"),
    ("1C1dGniuKp-kdW4y0ewvG9MCj9dWi9L_0", "03_Compiler_Design_Notes.pdf"),
    ("1gq0IcZmfVwcEFx2qhZfiyjU7VYm_EkOy", "04_Digital_Logic_Notes.pdf"),
    ("17HER2Sgi5iGffs1hl4q04RuNTJpbycou", "05_COA_Computer_Organization_Notes.pdf"),
    ("1FQGXMz5rs8I2gHAcUd1imHs0jzY37pVc", "06_Operating_Systems_Notes.pdf"),
    ("1r1p2sZiobgLdO1l7JalxTbQqH8on9w1G", "07_Computer_Networks_Notes.pdf"),
    ("1yHJtveVNJvWjuIfj-m9rGI5494kmf0RV", "08_DBMS_Databases_Notes.pdf"),
    ("1nXJPnbtA3-o-sJa7k0xAhq0nQrPWZip0", "09_Engineering_Mathematics_Notes.pdf"),
    ("1N977kn7HbW7hx3e7PUpo7YzrRVoI33ID", "10_Data_Structures_Notes.pdf"),
    ("1MGe343St6jek_U05GM4rJCfESFSEk7jY", "11_Algorithms_Notes.pdf"),
    ("17PuBw-i9CoC3e9L9iPGfitvNOXO7E4PH", "12_C_Programming_Notes.pdf"),
    ("1uWr8t5yEJJIL3SQsqTiORnHHCDsG4Vsj", "Silly_Mistakes_Log.pdf"),
    ("1KA-TtNUHi04z1A57u5qQQpVL_-df9RNf", "Preparation_Strategy.pdf")
]

def download_file(file_id: str, dest_path: Path):
    if dest_path.exists() and dest_path.stat().st_size > 50000:
        print(f"[Skipping] {dest_path.name} already downloaded ({dest_path.stat().st_size} bytes)")
        return True

    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    print(f"[Downloading] {dest_path.name} ...")
    try:
        resp = requests.get(url, stream=True, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        if resp.status_code == 200:
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            print(f"✓ Saved {dest_path.name} ({dest_path.stat().st_size} bytes)")
            return True
        else:
            print(f"✗ Failed {dest_path.name}: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error downloading {dest_path.name}: {e}")
        return False

def download_all_notes():
    print(f"Starting download of {len(NOTES_FILES)} handwritten subject notes...")
    success = 0
    for fid, filename in NOTES_FILES:
        dest = NOTES_DIR / filename
        if download_file(fid, dest):
            success += 1
    print(f"\nCompleted: {success}/{len(NOTES_FILES)} subject notes ready in {NOTES_DIR}")

if __name__ == "__main__":
    download_all_notes()
