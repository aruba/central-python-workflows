from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from paths import BASE_DIR

router = APIRouter()


def _resolve_results_folder(folder_name: str) -> Path:
    """Resolve and validate a results folder name, guarding against path traversal."""
    if not folder_name.startswith("results_"):
        raise HTTPException(status_code=400, detail="Invalid folder name")
    folder = (BASE_DIR / folder_name).resolve()
    if not folder.is_relative_to(BASE_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid folder name")
    return folder


@router.get("/api/results")
async def list_result_folders():
    folders = sorted(
        [d.name for d in BASE_DIR.iterdir() if d.is_dir() and d.name.startswith("results_")],
        reverse=True,
    )
    return {"folders": folders}


@router.get("/api/results/{folder_name}")
async def list_results(folder_name: str):
    folder = _resolve_results_folder(folder_name)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=404, detail="Results folder not found")
    files = [f.name for f in sorted(folder.iterdir()) if f.is_file()]
    return {"folder": folder_name, "files": files}


@router.get("/api/results/{folder_name}/{filename}")
async def download_result(folder_name: str, filename: str):
    folder = _resolve_results_folder(folder_name)
    path = (folder / filename).resolve()
    if not path.is_relative_to(folder):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(path), filename=filename)
