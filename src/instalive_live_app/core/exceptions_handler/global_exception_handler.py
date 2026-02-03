from fastapi import Request, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


# Handler for any unexpected errors
async def global_exception_handler(request: Request, exc: Exception):
    # Accessing app.debug from request.app
    debug_mode = request.app.debug
    logger.error(f"Global Error Captured: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "fail",
            "message": "An unexpected internal server error occurred. Please contact support.",
            "error_details": str(exc) if debug_mode else None
        },
    )
