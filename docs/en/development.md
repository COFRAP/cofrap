# Local development

## Start with Docker

Requirements: Python 3.12+, Docker with Compose, and `make`.
From the project root, run:

```sh
make setup
make functions-up
```

These commands create `.env` if it does not exist, install dependencies, and start:

- PostgreSQL on `127.0.0.1:55432` and the migrations;
- the three functions with the watchdog;
- an Nginx gateway on `127.0.0.1:8080`;
- the frontend at **http://localhost:8000**.

This mode does not install OpenFaaS or Kubernetes. To edit the frontend with
automatic reload, keep the other containers running and run:

```sh
docker compose -f compose.yaml -f compose.functions.yaml stop frontend
make dev
```

`OPENFAAS_GATEWAY_URL` tells the frontend where to find the gateway.
`PUBLIC_BASE_URL` must match in the frontend and functions so that QR links work.
`make functions-down` stops the containers and keeps the PostgreSQL volume.

On a phone, `localhost` points to the phone itself. Set
`PUBLIC_BASE_URL=http://COMPUTER_IP:8000` in `.env`, expose the frontend port on
that interface in `compose.functions.yaml`, and open **the same address** on the
computer and phone, on a trusted network. The database stays limited to loopback.
Use HTTPS and `COOKIE_SECURE=true` outside local development.

## Check changes

```sh
make check                # Style checks and unit tests
make test-integration     # Tests with a dedicated PostgreSQL instance on port 55433
```

See the [test limits](architecture.md#checks-and-limits).
Cluster deployment is described in [OpenFaaS](openfaas.md).

The tests in `tests/unit/functions` call the business logic of the three OpenFaaS
functions directly, without HTTP, Docker, or PostgreSQL. They use in-memory
storage, a fixed time, and the real encryption and TOTP tools. They cover success
and failure cases: registration, one-time password delivery, 2FA activation,
login, logout, expiry, and renewal.

To run only these tests:

```sh
.venv/bin/pytest tests/unit/functions -q
```
