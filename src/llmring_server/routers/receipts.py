from fastapi import APIRouter, Request, Path, HTTPException, Depends

from llmring_server.models.receipts import (
    ReceiptRequest,
    ReceiptResponse,
    Receipt,
    UnsignedReceipt,
)
from llmring_server.services.receipts import ReceiptsService
from llmring_server.dependencies import get_project_id


router = APIRouter(prefix="/api/v1/receipts", tags=["receipts"])


@router.post("/", response_model=ReceiptResponse)
async def store_receipt(request: Request, receipt_request: ReceiptRequest, api_key_id: str = Depends(get_project_id)):
    service = ReceiptsService(request.app.state.db)
    try:
        receipt_id = await service.store_receipt(api_key_id=api_key_id, receipt=receipt_request.receipt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ReceiptResponse(receipt_id=receipt_id, status="verified")


@router.get("/{receipt_id}", response_model=Receipt)
async def get_receipt(
    request: Request,
    receipt_id: str = Path(..., description="The receipt ID to retrieve"),
    api_key_id: str = Depends(get_project_id),
):
    service = ReceiptsService(request.app.state.db)
    receipt = await service.get_receipt(receipt_id, api_key_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@router.post("/issue", response_model=Receipt)
async def issue_receipt(request: Request, receipt: UnsignedReceipt):
    """Issue a signed receipt. Expects receipt without signature; returns with signature set.
    Requires server to have a configured signing key.
    """
    service = ReceiptsService(request.app.state.db)
    # Remove signature if provided
    payload = receipt.model_dump()
    payload.pop("signature", None)
    signature = service.issue_signature(payload)
    payload["signature"] = signature
    return Receipt(**payload)
