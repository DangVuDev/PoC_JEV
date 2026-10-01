from fastapi import APIRouter, Request

router = APIRouter(tags=["Providers"])


@router.get("/api/v1/providers")
def list_providers(request: Request) -> list[dict]:
    return request.app.state.registry.describe()
