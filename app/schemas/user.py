from pydantic import BaseModel, EmailStr


# البيانات القادمة من المستخدم (Request)
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


# البيانات التي نرجعها (Response)
class UserResponse(BaseModel):
    user_id: int
    name: str
    email: str

    class Config:
        from_attributes = True
        
class UserLogin(BaseModel):
    email: str
    password: str        

class RegisterRequest(BaseModel):
    company_name: str
    name: str
    email: str
    password: str    

class CompanyAdminLogin(BaseModel):
    email: str
    password: str    


from pydantic import BaseModel, EmailStr, field_validator
import re

class CompanyAdminRegister(BaseModel):
    company_name: str
    email: EmailStr
    password: str
    name: str

    @field_validator("password")
    def validate_password(cls, value):
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")

        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain uppercase letter")

        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain lowercase letter")

        if not re.search(r"\d", value):
            raise ValueError("Password must contain number")

        if not re.search(r"[!@#$%^&*]", value):
            raise ValueError("Password must contain special character")

        return value    