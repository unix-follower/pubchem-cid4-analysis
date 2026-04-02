from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

BIOACTIVITY_FIXTURE: dict[str, Any] = {
    "records": [
        {"aid": 743069, "assay": "Tox21 ER-alpha agonist", "activityValue": 355.1},
        {"aid": 743070, "assay": "Tox21 ER-alpha antagonist", "activityValue": 18.2},
        {"aid": 651820, "assay": "NCI growth inhibition", "activityValue": 92.4},
        {"aid": 540317, "assay": "Cell viability counter-screen", "activityValue": 112.7},
        {"aid": 504332, "assay": "ChEMBL potency panel", "activityValue": 8.6},
        {"aid": 720699, "assay": "Nuclear receptor confirmation", "activityValue": 61.9},
        {"aid": 743053, "assay": "Tox21 luciferase artifact", "activityValue": 140.4},
        {"aid": 743122, "assay": "Dose-response validation", "activityValue": 28.8},
        {"aid": 1259368, "assay": "Secondary pharmacology", "activityValue": 4.2},
        {"aid": 1345073, "assay": "Metabolism pathway screen", "activityValue": 205.5},
    ]
}

TAXONOMY_FIXTURE: dict[str, Any] = {
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

PATHWAY_FIXTURE: dict[str, Any] = {
    "graph": {
        "id": "glutathione-metabolism-iii",
        "title": "Glutathione Metabolism III",
        "directed": True,
        "nodes": [
            {"id": "step-1", "label": "Import precursor"},
            {"id": "step-2", "label": "Activate cysteine"},
            {"id": "step-3", "label": "Ligate glutamate"},
            {"id": "step-4", "label": "Add glycine"},
            {"id": "step-5", "label": "Reduce intermediate"},
            {"id": "step-6", "label": "Export product"},
        ],
        "edges": [
            {"id": "step-1-2", "source": "step-1", "target": "step-2"},
            {"id": "step-2-3", "source": "step-2", "target": "step-3"},
            {"id": "step-3-4", "source": "step-3", "target": "step-4"},
            {"id": "step-3-5", "source": "step-3", "target": "step-5"},
            {"id": "step-4-6", "source": "step-4", "target": "step-6"},
            {"id": "step-5-6", "source": "step-5", "target": "step-6"},
        ],
    }
}


def create_app(data_dir: Path) -> FastAPI:
    app = FastAPI(title="CID4 FastAPI", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health", response_model=None)
    def health(mode: Annotated[str | None, Query()] = None) -> Any:
        if mode == "error":
            return JSONResponse(
                status_code=503,
                content={
                    "message": "Transport error from FastAPI",
                    "source": "fastapi",
                    "timestamp": _timestamp(),
                },
            )

        return {
            "message": "FastAPI transport is healthy",
            "source": "fastapi",
            "timestamp": _timestamp(),
        }

    @app.get("/api/cid4/conformer/{index}", responses={404: {"description": "Unknown conformer"}})
    def conformer(index: int) -> FileResponse:
        if index < 1 or index > 6:
            raise HTTPException(status_code=404, detail=f"Unknown conformer {index}")
        return _json_file_response(data_dir / f"Conformer3D_COMPOUND_CID_4({index}).json")

    @app.get("/api/cid4/structure/2d", responses={404: {"description": "Missing JSON payload"}})
    def structure_2d() -> FileResponse:
        return _json_file_response(data_dir / "Structure2D_COMPOUND_CID_4.json")

    @app.get("/api/cid4/compound", responses={404: {"description": "Missing JSON payload"}})
    def compound() -> FileResponse:
        return _json_file_response(data_dir / "COMPOUND_CID_4.json")

    @app.get("/api/algorithms/pathway")
    def pathway() -> dict[str, Any]:
        return PATHWAY_FIXTURE

    @app.get("/api/algorithms/bioactivity")
    def bioactivity() -> dict[str, Any]:
        return BIOACTIVITY_FIXTURE

    @app.get("/api/algorithms/taxonomy")
    def taxonomy() -> dict[str, Any]:
        return TAXONOMY_FIXTURE

    return app


def _json_file_response(path: Path) -> FileResponse:
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Missing JSON payload {path.name}")
    return FileResponse(path, media_type="application/json")


def _timestamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
