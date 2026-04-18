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

class CompanyAdminRegister(BaseModel):
    company_name: str
    name: str
    email: str
    password: str    
class CompanyAdminLogin(BaseModel):
    email: str
    password: str    