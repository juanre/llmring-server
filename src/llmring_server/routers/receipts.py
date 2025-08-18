from fastapi import APIRouter, Request, Path, HTTPException

from llmring_server.models.receipts import ReceiptRequest, ReceiptResponse, Receipt
from llmring_server.services.receipts import ReceiptsService


router = APIRouter(prefix="/api/v1/receipts", tags=["receipts"]) 


@router.post("/", response_model=ReceiptResponse)
async def store_receipt(request: Request, receipt_request: ReceiptRequest):
    service = ReceiptsService(request.app.state.db)
    project_id = request.headers.get("X-Project-Key", "default")
    receipt_id = await service.store_receipt(api_key_id=project_id, receipt=receipt_request.receipt)
    return ReceiptResponse(receipt_id=receipt_id, status="verified")


@router.get("/{receipt_id}", response_model=Receipt)
async def get_receipt(request: Request, receipt_id: str = Path(..., description="The receipt ID to retrieve")):
    service = ReceiptsService(request.app.state.db)
    project_id = request.headers.get("X-Project-Key", "default")
    receipt = await service.get_receipt(receipt_id, project_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


