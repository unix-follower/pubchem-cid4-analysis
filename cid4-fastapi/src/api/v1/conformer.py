from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from src import constants


router = APIRouter()


@router.get("/api/v1/conformer/{index}")
async def conformer(index: int | str, request: Request):
    try:
        idx = int(index)
        if idx < 1 or idx > 6:
            raise ValueError("Index out of range")
    except ValueError:
        return JSONResponse(
            content={"message": f"Unknown conformer {index}"}, status_code=404
        )

    file_path = (
        request.app.state["data_dir"] / f"Conformer3D_COMPOUND_CID_4({index}).json"
    )
    body = file_path.read_text(encoding=constants.UTF_8)
    return Response(status_code=200, media_type="application/json", content=body)
