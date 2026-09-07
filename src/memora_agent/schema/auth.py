from pydantic import BaseModel, Field


class AuthCredentials(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=72)


class RegisterData(BaseModel):
    user_id: int
    username: str


class LoginData(BaseModel):
    token: str
    user_id: int
    username: str
    nickname: str
