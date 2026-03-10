from fastapi import APIRouter, Depends, HTTPException, UploadFile

from server.auth import require_auth
from server.services.salary import get_salary_data, get_salary_status, upload_salary_csv

router = APIRouter(prefix="/api/salary", dependencies=[Depends(require_auth)])


@router.post("/upload")
async def upload(file: UploadFile):
    content = await file.read()
    try:
        count = upload_salary_csv(content.decode("utf-8"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {e}")
    return {"count": count, "message": f"Uploaded {count} players"}


@router.get("")
def salary_list():
    df = get_salary_data()
    return df.to_dict(orient="records")


@router.get("/status")
def salary_status():
    return get_salary_status()
