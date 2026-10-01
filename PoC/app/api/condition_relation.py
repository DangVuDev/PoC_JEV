from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..schemas.request import DecideRequest
from ._respond import decide

router = APIRouter(tags=["P1 Condition Relation"])


@router.post("/api/v1/condition-relation/decide")
def decide_condition_relation(body: DecideRequest, request: Request) -> JSONResponse:
    return decide("p1", body, request)
