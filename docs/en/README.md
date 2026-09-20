# COFRAP — Secure identity

An authentication prototype with a generated password, one-time password delivery
through a QR code, TOTP setup, and credential renewal after six months.

The project uses **three Python OpenFaaS functions**, **PostgreSQL**, and a
**FastAPI / HTMX / Jinja2** frontend.

## Quick start

Requirements: Python 3.12+, Docker with Compose, and `make`.
From the project root, run:

```sh
make setup
make functions-up
```

Open the **[application](http://localhost:8000)** or the
[interactive API documentation](http://localhost:8000/docs).

These commands prepare `.env`, start PostgreSQL, run the migrations, and start
the functions and frontend. Locally, Nginx takes the place of the OpenFaaS gateway.
To stop the containers and keep the data, run `make functions-down`.

## Documentation

| Guide | Contents |
| --- | --- |
| [Architecture](architecture.md) | Components, user flow, security, and limits |
| [Database](database.md) | Each column, data types, tokens, and expiry times |
| [Local development](development.md) | Docker, local settings, and tests |
| [HTTP API](api.md) | Public routes and internal function calls |
| [OpenFaaS](openfaas.md) | Images, secrets, and deployment on k3s |
| [System diagram](diagrams/system-architecture.md) | Request flow and application components |
| [k3s cluster diagram](diagrams/k3s-cluster-architecture.md) | Three machines and cluster services |
| [Bundled library](third-party.md) | HTMX source and license |

[Documentation en français](../../README.md#documentation)
