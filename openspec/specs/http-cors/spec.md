# http-cors Specification

## Purpose

让浏览器前端可以从任意源站、用任意 HTTP 方法跨源调用本服务，从而接通文件预签名等接口的预检与正式请求。

## Requirements

### Requirement: Browser clients may call from any origin

本服务 MUST 在跨源响应中允许任意 Origin。对需要预检的请求，MUST 接受任意 HTTP 方法，并允许至少包含 `Content-Type` 与 `Authorization` 的请求头。本服务 MUST NOT 要求 cookie 凭证才能完成跨源访问。

#### Scenario: Cross-origin POST is allowed from any origin

- **WHEN** 浏览器从任意 Origin 对 `/files/presign` 发出带 `Content-Type: application/json` 的 POST
- **THEN** 响应包含允许该 Origin 的 CORS 头，且请求不被 CORS 策略拒绝

#### Scenario: Preflight allows any method

- **WHEN** 浏览器对任意已挂载路由发出 `OPTIONS` 预检，并询问任意 HTTP 方法
- **THEN** 预检成功，响应允许所询问的方法
