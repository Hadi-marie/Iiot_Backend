from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.coree.security import hash_password
from app.schemas.user import UserLogin
from app.coree.security import verify_password, create_access_token
from app.coree.security import get_current_user
from app.schemas.user import RegisterRequest
from app.models.company import Company
from app.schemas.user import CompanyAdminRegister
from app.models.company import Company
from app.models.company_admin import CompanyAdmin
from app.schemas.user import CompanyAdminLogin
from app.models.company_admin import CompanyAdmin




router = APIRouter()



@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):

    # 1️⃣ نجيب المستخدم من الداتا بيز
    db_user = db.query(User).filter(User.email == user.email).first()

    # 2️⃣ تحقق إذا موجود
    if not db_user:
        return {"error": "Invalid credentials"}

    # 3️⃣ تحقق من كلمة المرور
    if not verify_password(user.password, db_user.password_hash):
        return {"error": "Invalid credentials"}

    # 4️⃣ إنشاء token
    token = create_access_token({"user_id": db_user.user_id})

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "name": current_user.name
    }


@router.post("/register-company")
def register_company(data: CompanyAdminRegister, db: Session = Depends(get_db)):

    # 1️⃣ إنشاء الشركة
    new_company = Company(
        name=data.company_name,
        email=data.email
    )

    db.add(new_company)
    db.commit()
    db.refresh(new_company)

    # 2️⃣ إنشاء admin وربطه بالشركة
    new_admin = CompanyAdmin(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        company_id=new_company.company_id
    )

    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return {
        "message": "Company and admin created",
        "company_id": new_company.company_id,
        "admin_id": new_admin.admin_id
    }


@router.post("/login-company")
def login_company(data: CompanyAdminLogin, db: Session = Depends(get_db)):

    # 1️⃣ نجيب admin
    admin = db.query(CompanyAdmin).filter(CompanyAdmin.email == data.email).first()

    # 2️⃣ تحقق
    if not admin:
        return {"error": "Invalid credentials"}

    if not verify_password(data.password, admin.password_hash):
        return {"error": "Invalid credentials"}

    # 3️⃣ إنشاء token (مهم جدًا)
    token = create_access_token({
        "admin_id": admin.admin_id,
        "company_id": admin.company_id
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }