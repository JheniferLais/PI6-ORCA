"""
Corpos das requisições. Os nomes seguem as colunas do banco (name, email,
password). Nomes antigos continuam aceitos para não quebrar quem já chamava a
API: nome, senha e, no lugar de email, identifier/identificador.
"""
import re

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl, field_validator


# formato básico algo@dominio.ext, sem espaços (o mesmo que o site valida)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
EMAIL_ALIASES = AliasChoices("email", "identifier", "identificador")


def normalizar_email(v: str) -> str:
    """E-mail sem espaços nas pontas e em minúsculas: é assim que fica no banco."""
    return v.strip().lower()


class UserCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=120, validation_alias=AliasChoices("name", "nome"))
    email: str = Field(min_length=3, max_length=254, validation_alias=EMAIL_ALIASES)
    password: str = Field(min_length=8, max_length=128, validation_alias=AliasChoices("password", "senha"))

    @field_validator("name")
    @classmethod
    def sem_espacos_nas_pontas(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("não pode ser vazio")
        return v

    @field_validator("email")
    @classmethod
    def email_valido(cls, v: str) -> str:
        v = normalizar_email(v)
        if not EMAIL_RE.match(v):
            raise ValueError("e-mail inválido")
        return v


class UserLogin(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str = Field(min_length=1, max_length=254, validation_alias=EMAIL_ALIASES)
    password: str = Field(min_length=1, validation_alias=AliasChoices("password", "senha"))

    @field_validator("email")
    @classmethod
    def email_normalizado(cls, v: str) -> str:
        return normalizar_email(v)


class LogCreate(BaseModel):
    url: HttpUrl
    level: str = Field(min_length=1, max_length=50)
    reason: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
