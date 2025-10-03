from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import PlainTextResponse, JSONResponse
from pgdbm import AsyncDatabaseManager

from llmring_server.config import Settings
from llmring_server.dependencies import get_db, get_project_id, get_settings
from llmring_server.models.receipts import (
    BatchReceipt,
    Receipt,
    ReceiptGenerationRequest,
    ReceiptGenerationResponse,
    ReceiptListResponse,
    ReceiptRequest,
    ReceiptResponse,
    UnsignedReceipt,
)
from llmring_server.services.receipts import ReceiptsService

router = APIRouter(prefix="/api/v1/receipts", tags=["receipts"])


async def get_db_optional(request: Request) -> Optional[AsyncDatabaseManager]:
    """Get database manager without requiring authentication."""
    if not hasattr(request.app.state, "db") or not request.app.state.db:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return request.app.state.db


# Public endpoints (no authentication) - MUST come before /{receipt_id} route
@router.get("/public-key.pem", response_class=PlainTextResponse)
async def get_public_key_pem(db: AsyncDatabaseManager = Depends(get_db_optional)):
    """
    Get the server's public key in PEM format for receipt verification.

    This endpoint does not require authentication as the public key is meant
    to be publicly accessible for receipt verification.
    """
    settings = Settings()
    service = ReceiptsService(db, settings)

    try:
        pem_key = service.get_public_key_pem()
        return PlainTextResponse(content=pem_key, media_type="application/x-pem-file")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/public-keys.json")
async def get_public_keys_json(db: AsyncDatabaseManager = Depends(get_db_optional)):
    """
    Get the server's public keys in JSON format.

    Returns a JSON object with the current public key(s) and key ID.
    This endpoint does not require authentication.
    """
    settings = Settings()
    service = ReceiptsService(db, settings)

    if not settings.receipts_public_key_base64:
        raise HTTPException(status_code=500, detail="Public key not configured")

    return JSONResponse(
        content={
            "keys": [
                {
                    "key_id": settings.receipts_key_id or "default",
                    "public_key": settings.receipts_public_key_base64,
                    "algorithm": "Ed25519",
                    "format": "base64url",
                }
            ],
            "current_key_id": settings.receipts_key_id or "default",
        }
    )


@router.post("/verify")
async def verify_receipt(
    receipt: Receipt,
    db: AsyncDatabaseManager = Depends(get_db_optional),
    settings: Settings = Depends(get_settings),
):
    """
    Verify a receipt's signature.

    Returns verification status. Does not require authentication.
    """
    service = ReceiptsService(db, settings)

    try:
        is_valid = service._verify_signature(receipt)
        return {
            "receipt_id": receipt.receipt_id,
            "valid": is_valid,
            "algorithm": "Ed25519",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verification failed: {e}")


# Authenticated endpoints (require X-API-Key header)
@router.get("/", response_model=ReceiptListResponse)
async def list_receipts(
    limit: int = Query(100, ge=1, le=1000, description="Maximum receipts to return"),
    offset: int = Query(0, ge=0, description="Number of receipts to skip"),
    api_key_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    """List receipts for the authenticated API key with pagination."""
    settings = Settings()
    service = ReceiptsService(db, settings)

    receipts, total = await service.list_receipts(api_key_id, limit, offset)

    return ReceiptListResponse(receipts=receipts, total=total, limit=limit, offset=offset)


@router.post("/", response_model=ReceiptResponse)
async def store_receipt(
    receipt_request: ReceiptRequest,
    api_key_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    """Store an externally-generated signed receipt."""
    settings = Settings()
    service = ReceiptsService(db, settings)
    try:
        receipt_id = await service.store_receipt(
            api_key_id=api_key_id, receipt=receipt_request.receipt
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ReceiptResponse(receipt_id=receipt_id, status="verified")


@router.get("/uncertified")
async def get_uncertified_logs(
    limit: int = Query(100, ge=1, le=1000, description="Maximum logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
    api_key_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Get logs that haven't been certified by any receipt.

    This endpoint helps users identify which conversations/usage logs
    don't yet have a receipt. Useful for periodic certification workflows.

    Returns:
        List of uncertified logs with pagination info
    """
    service = ReceiptsService(db, settings)

    try:
        logs, total = await service.get_uncertified_logs(
            api_key_id=api_key_id,
            limit=limit,
            offset=offset,
        )

        return {
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch uncertified logs: {str(e)}")


@router.get("/{receipt_id}", response_model=Receipt)
async def get_receipt(
    receipt_id: str = Path(..., description="The receipt ID to retrieve"),
    api_key_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
):
    """Get a specific receipt by ID."""
    settings = Settings()
    service = ReceiptsService(db, settings)
    receipt = await service.get_receipt(receipt_id, api_key_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@router.post("/issue", response_model=Receipt)
async def issue_receipt(
    receipt: UnsignedReceipt,
    db: AsyncDatabaseManager = Depends(get_db),
):
    """
    Issue a signed receipt.

    Expects an unsigned receipt; returns a signed receipt.
    Requires server to have configured signing keys.
    """
    settings = Settings()
    service = ReceiptsService(db, settings)

    # Sign the receipt
    payload = receipt.model_dump()
    payload.pop("signature", None)
    signature = service._issue_signature(payload)
    payload["signature"] = signature

    return Receipt(**payload)


# =====================================================
# Phase 7.5: On-Demand Receipt Generation
# =====================================================


@router.post("/generate", response_model=ReceiptGenerationResponse)
async def generate_receipt(
    request: ReceiptGenerationRequest,
    api_key_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Generate a receipt on-demand for logs/conversations.

    This endpoint implements Phase 7.5 on-demand receipt generation.
    Unlike Phase 7 where receipts were generated automatically with every log,
    this allows users to generate receipts when needed for compliance/certification.

    Supports four modes:
    1. **Single conversation**: Provide `conversation_id`
    2. **Date range (batch)**: Provide `start_date` and `end_date`
    3. **Specific logs**: Provide `log_ids` array
    4. **Since last receipt**: Set `since_last_receipt=true`

    The generated receipt certifies the specified logs and is signed with Ed25519.
    For batch receipts, aggregated statistics are included.

    Returns:
        ReceiptGenerationResponse with the signed receipt and count of certified items
    """
    service = ReceiptsService(db, settings)

    try:
        receipt, certified_count = await service.generate_on_demand_receipt(
            api_key_id=api_key_id,
            request=request,
        )

        return ReceiptGenerationResponse(
            receipt=receipt,
            certified_count=certified_count,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate receipt: {str(e)}")


@router.post("/preview")
async def preview_receipt(
    request: ReceiptGenerationRequest,
    api_key_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Preview what a receipt would certify without generating it.

    This endpoint allows users to see what logs would be included in a receipt
    and view aggregate statistics before committing to generating the receipt.

    Useful for verifying that the right logs will be certified.

    Returns:
        Preview summary with counts, costs, and breakdowns
    """
    service = ReceiptsService(db, settings)

    try:
        preview = await service.preview_receipt(
            api_key_id=api_key_id,
            request=request,
        )
        return preview

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preview receipt: {str(e)}")


@router.get("/{receipt_id}/logs")
async def get_receipt_logs(
    receipt_id: str = Path(..., description="The receipt ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
    api_key_id: str = Depends(get_project_id),
    db: AsyncDatabaseManager = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """
    Get all logs certified by a specific receipt.

    This endpoint returns the full details of all conversations/usage logs
    that were certified by the specified receipt. Useful for audit trails
    and verifying what a receipt covers.

    Returns:
        List of logs certified by the receipt with pagination info
    """
    service = ReceiptsService(db, settings)

    try:
        logs, total = await service.get_logs_for_receipt(
            receipt_id=receipt_id,
            api_key_id=api_key_id,
            limit=limit,
            offset=offset,
        )

        return {
            "receipt_id": receipt_id,
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch receipt logs: {str(e)}")
