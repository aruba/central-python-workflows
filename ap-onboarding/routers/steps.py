from dataclasses import asdict

from fastapi import APIRouter

from steps import STEPS

router = APIRouter()


@router.get("/api/steps")
async def get_steps():
    return [
        {
            "key": step.key,
            "label": step.label,
            "description": step.description,
            "field": asdict(step.field),
        }
        for step in STEPS
    ]
