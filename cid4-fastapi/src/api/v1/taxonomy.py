from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter()

_TAXONOMY_FIXTURE: dict[str, object] = {
    "organisms": [
        {"taxonomyId": 9913, "sourceOrganism": "Bos taurus"},
        {"taxonomyId": 9913, "sourceOrganism": "Bos taurus"},
        {"taxonomyId": 9823, "sourceOrganism": "Sus scrofa"},
        {"taxonomyId": 9031, "sourceOrganism": "Gallus gallus"},
        {"taxonomyId": 9031, "sourceOrganism": "Gallus gallus"},
        {"taxonomyId": 9103, "sourceOrganism": "Meleagris gallopavo"},
        {"taxonomyId": 9986, "sourceOrganism": "Oryctolagus cuniculus"},
        {"taxonomyId": 9685, "sourceOrganism": "Felis catus"},
    ]
}


@router.get("/api/v1/taxonomy")
async def taxonomy(_: Request) -> JSONResponse:
    return JSONResponse(status_code=200, content=_TAXONOMY_FIXTURE)
