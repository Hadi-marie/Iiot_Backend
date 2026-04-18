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