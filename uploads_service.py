"""
File upload service for managing quotations and documents.
"""

import json
import shutil
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
import uuid

from models import UploadMetadata
from storage_new import UPLOADS_BASE_DIR, ensure_directories


def get_upload_path(client_id: str, project_id: str, scenario_id: str, level: str, item_id: Optional[str] = None) -> Path:
    """Get the upload path for a given level."""
    ensure_directories()
    
    if level == "project":
        return UPLOADS_BASE_DIR / client_id / project_id / "project"
    elif level == "scenario":
        return UPLOADS_BASE_DIR / client_id / project_id / scenario_id / "scenario"
    elif level == "item" and item_id:
        return UPLOADS_BASE_DIR / client_id / project_id / scenario_id / "items" / item_id
    else:
        raise ValueError(f"Invalid level: {level}")


def save_upload_metadata(metadata: UploadMetadata, upload_path: Path):
    """Save upload metadata JSON file."""
    metadata_file = upload_path / f"{metadata.upload_id}.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata.to_dict(), f, indent=2, ensure_ascii=False)


def load_upload_metadata(upload_id: str, upload_path: Path) -> Optional[UploadMetadata]:
    """Load upload metadata."""
    metadata_file = upload_path / f"{upload_id}.json"
    if not metadata_file.exists():
        return None
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            return UploadMetadata.from_dict(json.load(f))
    except (json.JSONDecodeError, IOError):
        return None


def upload_file(
    file_content: bytes,
    filename: str,
    client_id: str,
    project_id: str,
    scenario_id: str,
    level: str,
    label: str = "",
    tags: List[str] = None,
    item_id: Optional[str] = None,
    supplier: Optional[str] = None,
    incoterm: Optional[str] = None
) -> UploadMetadata:
    """Upload a file and save metadata."""
    ensure_directories()
    
    upload_path = get_upload_path(client_id, project_id, scenario_id, level, item_id)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Generate upload ID
    upload_id = str(uuid.uuid4())
    
    # Save file
    file_path = upload_path / filename
    with open(file_path, 'wb') as f:
        f.write(file_content)
    
    # Create metadata
    metadata = UploadMetadata(
        upload_id=upload_id,
        filename=filename,
        label=label or filename,
        tags=tags or [],
        upload_date=datetime.now().isoformat(),
        level=level,
        linked_item_ids=[item_id] if item_id else [],
        supplier=supplier,
        incoterm=incoterm
    )
    
    # Save metadata
    save_upload_metadata(metadata, upload_path)
    
    return metadata


def list_uploads(
    client_id: str,
    project_id: str,
    scenario_id: str,
    level: Optional[str] = None,
    item_id: Optional[str] = None,
    tag_filter: Optional[str] = None
) -> List[UploadMetadata]:
    """List all uploads matching filters."""
    ensure_directories()
    
    uploads = []
    
    # Determine which paths to search
    paths_to_search = []
    
    if level == "project":
        paths_to_search.append(get_upload_path(client_id, project_id, scenario_id, "project"))
    elif level == "scenario":
        paths_to_search.append(get_upload_path(client_id, project_id, scenario_id, "scenario"))
    elif level == "item" and item_id:
        paths_to_search.append(get_upload_path(client_id, project_id, scenario_id, "item", item_id))
    else:
        # Search all levels
        paths_to_search.append(get_upload_path(client_id, project_id, scenario_id, "project"))
        paths_to_search.append(get_upload_path(client_id, project_id, scenario_id, "scenario"))
        items_path = UPLOADS_BASE_DIR / client_id / project_id / scenario_id / "items"
        if items_path.exists():
            for item_dir in items_path.iterdir():
                if item_dir.is_dir():
                    paths_to_search.append(item_dir)
    
    # Load metadata from all paths
    for upload_path in paths_to_search:
        if not upload_path.exists():
            continue
        
        for metadata_file in upload_path.glob("*.json"):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = UploadMetadata.from_dict(json.load(f))
                    
                    # Apply filters
                    if tag_filter and tag_filter not in metadata.tags:
                        continue
                    if item_id and item_id not in metadata.linked_item_ids:
                        continue
                    
                    uploads.append(metadata)
            except (json.JSONDecodeError, IOError):
                continue
    
    return uploads


def delete_upload(
    upload_id: str,
    client_id: str,
    project_id: str,
    scenario_id: str,
    level: str,
    item_id: Optional[str] = None
):
    """Delete an upload and its metadata."""
    upload_path = get_upload_path(client_id, project_id, scenario_id, level, item_id)
    
    # Load metadata to get filename
    metadata = load_upload_metadata(upload_id, upload_path)
    if metadata:
        # Delete file
        file_path = upload_path / metadata.filename
        if file_path.exists():
            file_path.unlink()
        
        # Delete metadata
        metadata_file = upload_path / f"{upload_id}.json"
        if metadata_file.exists():
            metadata_file.unlink()


def attach_upload_to_item(
    upload_id: str,
    client_id: str,
    project_id: str,
    scenario_id: str,
    item_id: str
):
    """Attach an existing upload to an item."""
    # Find the upload in all possible locations
    for level in ["project", "scenario", "item"]:
        try:
            upload_path = get_upload_path(client_id, project_id, scenario_id, level)
            metadata = load_upload_metadata(upload_id, upload_path)
            if metadata:
                # Add item_id to linked_item_ids
                if item_id not in metadata.linked_item_ids:
                    metadata.linked_item_ids.append(item_id)
                    save_upload_metadata(metadata, upload_path)
                return
        except ValueError:
            continue
