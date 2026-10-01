from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..schemas.request import DecideRequest
from ._respond import decide

router = APIRouter(tags=["P2 Performer Lane"])


@router.post("/api/v1/performer-lane/decide")
def decide_performer_lane(body: DecideRequest, request: Request) -> JSONResponse:
    return decide("p2", body, request)
