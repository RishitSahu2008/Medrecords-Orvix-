"""
storage.py
Prototype file-storage layer. Right now it saves files to a local folder
structured as:  storage/<app_id>/<category>/<filename>

This mimics what a "Google Drive folder per patient" would look like.
When you're ready to move to real Google Drive, you only need to change
the functions in this file (save_file / get_file_path / list_files) -
nothing else in the app needs to change, since every other module only
calls these functions.
"""

import os
import shutil
from datetime import datetime

BASE_STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")


def _safe_filename(original_filename):
    """Prefix with a timestamp so files never overwrite each other."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    name = os.path.basename(original_filename).replace(" ", "_")
    return f"{timestamp}_{name}"


def save_file(app_id, category, uploaded_file):
    """
    Save an uploaded file (Streamlit UploadedFile object) into
    storage/<app_id>/<category>/ and return the path that should be stored in the DB.

    category: 'reports' or 'prescriptions'
    """
    folder = os.path.join(BASE_STORAGE_DIR, app_id, category)
    os.makedirs(folder, exist_ok=True)

    filename = _safe_filename(uploaded_file.name)
    full_path = os.path.join(folder, filename)

    with open(full_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return full_path


def get_file_path(stored_path):
    """Given the path stored in the DB, return the actual path to read from."""
    return stored_path


def delete_file(stored_path):
    if os.path.exists(stored_path):
        os.remove(stored_path)


def folder_size_info(app_id):
    """Just a helper - not essential, but useful to show storage usage on the dashboard."""
    folder = os.path.join(BASE_STORAGE_DIR, app_id)
    if not os.path.exists(folder):
        return 0
    total = 0
    for dirpath, _, filenames in os.walk(folder):
        for f in filenames:
            total += os.path.getsize(os.path.join(dirpath, f))
    return total
