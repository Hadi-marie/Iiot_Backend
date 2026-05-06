from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.network import Network
from app.coree.security import get_current_admin
from app.utils.subscription import check_subscription

router = APIRouter()


# 🎯 إنشاء شبكة للشركة
@router.post("/")
def create_network(
    ip_range: str,
    current_admin=Depends(get_current_admin),
    db: Session = Depends(get_db)
):

    # 🔥 تحقق الاشتراك
    check_subscription(db, current_admin.company_id)

    # 🔥 تحقق إذا الشركة عندها شبكة مسبقًا
    existing_network = db.query(Network).filter(
        Network.company_id == current_admin.company_id
    ).first()

    # ❌ ممنوع أكثر من شبكة
    if existing_network:
        raise HTTPException(
            status_code=400,
            detail="Network already exists"
        )

    # 🔥 إنشاء الشبكة
    new_network = Network(
        company_id=current_admin.company_id,
        ip_range=ip_range
    )

    db.add(new_network)
    db.commit()
    db.refresh(new_network)

    return {
        "message": "Network created successfully",
        "network_public_id": new_network.public_id
    }