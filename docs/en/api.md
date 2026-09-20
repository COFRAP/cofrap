# HTTP API

This page describes the frontend's public API and the functions' internal routes.

## Frontend JSON API

The interactive documentation is available at [/docs](http://localhost:8000/docs)
locally. The OpenAPI schema is available at `/openapi.json`.

| Method and route | Purpose | Authorization |
| --- | --- | --- |
| `POST /api/users` | Create the account and password | `username` |
| `POST /api/password-deliveries/redeem` | Use the password delivery token | `token` in the JSON body |
| `POST /api/enrollment/totp` | Set up TOTP | Enrollment Bearer token |
| `POST /api/enrollment/confirm` | Confirm and activate the account | Enrollment Bearer token + `code` |
| `POST /api/auth/login` | Log in or request renewal | `username`, `password`, `code` |
| `POST /api/credentials/renew` | Replace both factors | Renewal Bearer token |
| `GET /api/me` | Read your account | Session Bearer token |
| `POST /api/auth/logout` | Revoke the session | Session Bearer token |
| `GET /health/live` | Check the process | None |
| `GET /health/ready` | Check the functions and PostgreSQL | None |

Registration returns `enrollment_token`, `delivery_url`, `delivery_qr`, and
`expires_at`. The fragment of `delivery_url` holds the token for the delivery
endpoint. QR codes are PNG images in data URLs. The password only appears in the
delivery response, never in the registration response.

Login returns HTTP 200 with `status=authenticated` and a session token, or
`status=renewal_required` and a token that only allows renewal. This second result
**does not allow** access to `/api/me`. Send enrollment, renewal, and session
tokens with `Authorization: Bearer …`. The server checks their expiry times.

Errors use the format `{"error":{"code":"…","message":"…"}}`:
401 for an invalid factor or token, 409 for a username already in use or incomplete
activation, and 422 for invalid input. Errors do not copy input data into the
response. HTMX errors keep the form and appear in its alert area.

## Function HTTP contract

These routes are internal. The gateway adds the prefix `/function/<name>`.
All operations below use POST with a JSON body.
The frontend calls these routes through the OpenFaaS gateway.

| Function | Route | Input | Result |
| --- | --- | --- | --- |
| generate-password | `/register` | `username` | Account, tokens, delivery link, and QR code |
| generate-password | `/redeem` | Delivery `token` | Password, shown only once |
| generate-password | `/inspect` | Enrollment `token` | Account and delivery status |
| generate-password | `/qr` | Delivery `token` | Link and QR code, without checking the token in the database or using it up |
| generate-password | `/renew` | Renewal `token` | New activation flow |
| generate-2fa | `/setup` | Enrollment `token` | Secret, TOTP URI, and QR code |
| generate-2fa | `/confirm` | Enrollment `token`, `code` | Activated account |
| authenticate | `/login` | `username`, `password`, `code` | Session or `renewal_required` |
| authenticate | `/me` | Session `token` | Account |
| authenticate | `/logout` | Session `token` | HTTP 204 |

The functions validate input. Business rule errors use the format
`{"error":{"code":"…","message":"…"}}`. The frontend returns HTTP 503 if the
backend is unavailable. It does not retry calls automatically.
