from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter()


_BIOACTIVITY_FIXTURE: dict[str, object] = {
    "records": [
        {"aid": 743069, "assay": "Tox21 ER-alpha agonist", "activityValue": 355.1},
        {"aid": 743070, "assay": "Tox21 ER-alpha antagonist", "activityValue": 18.2},
        {"aid": 651820, "assay": "NCI growth inhibition", "activityValue": 92.4},
        {
            "aid": 540317,
            "assay": "Cell viability counter-screen",
            "activityValue": 112.7,
        },
        {"aid": 504332, "assay": "ChEMBL potency panel", "activityValue": 8.6},
        {
            "aid": 720699,
            "assay": "Nuclear receptor confirmation",
            "activityValue": 61.9,
        },
        {"aid": 743053, "assay": "Tox21 luciferase artifact", "activityValue": 140.4},
        {"aid": 743122, "assay": "Dose-response validation", "activityValue": 28.8},
        {"aid": 1259368, "assay": "Secondary pharmacology", "activityValue": 4.2},
        {"aid": 1345073, "assay": "Metabolism pathway screen", "activityValue": 205.5},
    ]
}


@router.get("/api/v1/bioactivity")
async def bioactivity(_: Request) -> JSONResponse:
    return JSONResponse(status_code=200, content=_BIOACTIVITY_FIXTURE)
