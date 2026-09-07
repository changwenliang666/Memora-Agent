from fastapi import APIRouter

from memora_agent.core.auth import create_access_token, verify_password
from memora_agent.schema.auth import AuthCredentials, LoginData, RegisterData
from memora_agent.schema.bizcode import BizCode
from memora_agent.schema.response import ResponseStructure
from memora_agent.service.user_service import UserAlreadyExistsError, userService

auth_router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@auth_router.post("/register", response_model=ResponseStructure[RegisterData])
async def register(body: AuthCredentials) -> ResponseStructure[RegisterData]:
    try:
        user = await userService.create_user(body.username, body.password)
    except UserAlreadyExistsError:
        return ResponseStructure[RegisterData](
            code=BizCode.USERNAME_ALREADY_EXISTS.value,
            message="用户名已存在",
        )
    return ResponseStructure[RegisterData](
        message="注册成功",
        data=RegisterData(user_id=user.id, username=user.username),
    )


@auth_router.post("/login", response_model=ResponseStructure[LoginData])
async def login(body: AuthCredentials) -> ResponseStructure[LoginData]:
    user = await userService.get_user_by_username(body.username)
    if user is None or not verify_password(body.password, user.password):
        return ResponseStructure[LoginData](
            code=BizCode.INVALID_CREDENTIALS.value,
            message="用户名或密码错误",
        )
    token = create_access_token(user.id, user.username)
    return ResponseStructure[LoginData](
        message="登录成功",
        data=LoginData(token=token, user_id=user.id, username=user.username,nickname=user.nickname),
    )
