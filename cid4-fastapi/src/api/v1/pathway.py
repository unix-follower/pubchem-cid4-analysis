from fastapi import APIRouter, Request, Response
from src import constants


router = APIRouter()

# PATHWAY_FIXTURE: dict[str, object] = {
#     "graph": {
#         "id": "glutathione-metabolism-iii",
#         "title": "Glutathione Metabolism III",
#         "directed": True,
#         "nodes": [
#             {"id": "step-1", "label": "Import precursor"},
#             {"id": "step-2", "label": "Activate cysteine"},
#             {"id": "step-3", "label": "Ligate glutamate"},
#             {"id": "step-4", "label": "Add glycine"},
#             {"id": "step-5", "label": "Reduce intermediate"},
#             {"id": "step-6", "label": "Export product"},
#         ],
#         "edges": [
#             {"id": "step-1-2", "source": "step-1", "target": "step-2"},
#             {"id": "step-2-3", "source": "step-2", "target": "step-3"},
#             {"id": "step-3-4", "source": "step-3", "target": "step-4"},
#             {"id": "step-3-5", "source": "step-3", "target": "step-5"},
#             {"id": "step-4-6", "source": "step-4", "target": "step-6"},
#             {"id": "step-5-6", "source": "step-5", "target": "step-6"},
#         ],
#     }
# }


@router.get("/api/v1/pathway")
async def pathway(request: Request) -> Response:
    file_path = request.app.state["data_dir"] / "PATHWAY_PathwayID_1186280.json"
    body = file_path.read_text(encoding=constants.UTF_8)
    return Response(status_code=200, media_type="application/json", content=body)
