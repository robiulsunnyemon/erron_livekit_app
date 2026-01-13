from fastapi import FastAPI,status
from erron_live_app.streaming.routers.streaming import router as stream_router


app = FastAPI()


@app.get("/",status_code=status.HTTP_200_OK,tags=["Health"])
async def check_health():
    return {"message":"Api is working perfectly"}


app.include_router(stream_router,prefix="/api/v1")