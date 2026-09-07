## 1. 信封与业务码

- [x] 1.1 在 `BizCode` 增加 `USERNAME_ALREADY_EXISTS = 1001` 与 `INVALID_CREDENTIALS = 1002`，保留 `SUCCESS = 0`；确认枚举可被 `ResponseStructure` 以 `.value` 写入 `code`
- [x] 1.2 将 `ResponseStructure.data` 改为可选（默认 `None`），`to_dict` 直接输出整型 `code` 而不访问 `.value`。确认 `files/complete` 成功响应仍带 `data` 且测试不因可选字段失败

## 2. 登录注册接口

- [x] 2.1 注册：成功返回 `code=SUCCESS` 与用户载荷；用户名冲突返回 HTTP 200、`code=USERNAME_ALREADY_EXISTS`、`data` 为空，不再抛 HTTP 409。更新 `tests/api/test_auth.py` 对应断言并执行通过
- [x] 2.2 登录：成功返回 `code=SUCCESS` 与 token；错误口令或用户不存在返回 HTTP 200、`code=INVALID_CREDENTIALS`、`data` 为空且无 JWT，不再抛 HTTP 401。更新测试并执行通过
- [x] 2.3 README 登录注册说明改为看信封 `code`（0 成功）；确认受保护路由无 token 仍为 HTTP 401。执行 `uv run pytest tests/api/test_auth.py tests/api/test_files.py` 确认 auth 与 files 用例全绿
