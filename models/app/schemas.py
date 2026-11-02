from pydantic import BaseModel, Field, HttpUrl


class UserCreate(BaseModel):
    identificador: str = Field(min_length=3, max_length=100)
    senha: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    identificador: str
    senha: str


class LogCreate(BaseModel):
    url: HttpUrl
    level: str = Field(min_length=1, max_length=50)
    reason: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"