"""
audit.py
--------
Admin Audit Trail Routes.
Provides paginated querying, filtering, and CSV export of immutable audit logs.
Mutation endpoints are intentionally omitted to guarantee append-only integrity.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, Response
from database.mongodb import get_db
from services.auth_service import get_current_user, require_role
from services.audit_service import get_audit_logs, generate_audit_csv

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("")
async def list_audit_logs(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(require_role(["ADMIN", "OPERATOR"])),
    db=Depends(get_db),
):
    """Returns paginated audit trail logs. Restricted to ADMIN and OPERATOR."""
    return await get_audit_logs(
        db=db,
        page=page,
        limit=limit,
        action=action,
        target_type=target_type,
        username=username,
        result=result,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )


@router.get("/export/csv")
async def export_audit_csv(
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(require_role(["ADMIN"])),
    db=Depends(get_db),
):
    """Exports audit trail as a downloadable RFC-4180 CSV file. Admin only."""
    res = await get_audit_logs(
        db=db,
        page=1,
        limit=5000,
        action=action,
        target_type=target_type,
        username=username,
        result=result,
        start_date=start_date,
        end_date=end_date,
    )
    csv_data = generate_audit_csv(res["items"])
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="b-shield-audit-trail.csv"'},
    )
