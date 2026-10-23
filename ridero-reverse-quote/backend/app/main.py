import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import HealthResponse, ReverseQuoteRequest, ReverseQuoteResponse
from app.services.lease_math import (
    calculate_reverse_quote_fixed_residual,
    calculate_reverse_quote_percent_residual,
)

app = FastAPI(title="Ridero Reverse Quote API", version="0.1.0")

allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/quote/reverse", response_model=ReverseQuoteResponse)
def reverse_quote(request: ReverseQuoteRequest) -> ReverseQuoteResponse:
    common = request.model_dump(exclude={"residual_value", "residual_percent"})
    try:
        if request.residual_value is not None:
            mode = "fixed_residual"
            result = calculate_reverse_quote_fixed_residual(residual_value=request.residual_value, **common)
        else:
            mode = "percent_residual"
            result = calculate_reverse_quote_percent_residual(residual_percent=request.residual_percent, **common)
    except (ValueError, TypeError) as exc:
        # Same shape as FastAPI's own request-validation errors.
        raise HTTPException(
            status_code=422,
            detail=[{"type": "lease_validation_error", "loc": ["body"], "msg": str(exc)}],
        ) from exc
    return ReverseQuoteResponse(mode=mode, **asdict(result))
