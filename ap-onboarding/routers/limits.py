from fastapi import APIRouter

from utils.validate_workflow_variables_template import get_max_devices_per_run

router = APIRouter()


@router.get("/api/limits")
async def get_limits():
    return {"max_devices": get_max_devices_per_run()}
