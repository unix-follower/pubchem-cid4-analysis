from fastapi import APIRouter, Request, Response
from src import constants


router = APIRouter()


@router.get("/api/v1/compound")
async def compound(request: Request) -> Response:
    file_path = request.app.state["data_dir"] / "COMPOUND_CID_4.json"
    body = file_path.read_text(encoding=constants.UTF_8)
    return Response(status_code=200, media_type="application/json", content=body)
