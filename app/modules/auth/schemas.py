from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class RegisterInitResponse(BaseModel):
    message: str
    email: EmailStr


class VerifyRegisterOtp(BaseModel):
    email: EmailStr
    otp_code: str = Field(min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str | None = None
    email: EmailStr | None = None


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str | None = None
    is_verified: bool

    model_config = {"from_attributes": True}


class GoogleProfileInspectResponse(BaseModel):
    """Profile fields returned by Google (dev-only inspect endpoint)."""

    extracted_name: str | None = None
    id_token_fields: dict
    userinfo_fields: dict | None = None
