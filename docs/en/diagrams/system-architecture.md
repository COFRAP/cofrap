# COFRAP system architecture

```mermaid
flowchart LR
    B["User<br/>Browser with HTMX"]

    subgraph K3S["Kubernetes cluster — k3s"]
        I["HTTPS entry point<br/>Traefik"]
        F["Frontend · 2 replicas<br/>FastAPI / Jinja2<br/>HTML pages and JSON API"]
        G["OpenFaaS gateway<br/>Request routing"]

        subgraph FN["Python functions — separate images"]
            P["generate-password<br/>Registration and renewal<br/>One-time password delivery"]
            T["generate-2fa<br/>TOTP setup<br/>Account activation"]
            A["authenticate<br/>Login with password + TOTP<br/>Session and logout"]
        end

        DB[("PostgreSQL 17<br/>Shared database · 1 instance")]
        V[("Persistent volume")]

        I -->|"HTTP"| F
        F -->|"HTTP / JSON"| G
        G -->|"HTTP"| P
        G -->|"HTTP"| T
        G -->|"HTTP"| A

        P -->|"SQL"| DB
        T -->|"SQL"| DB
        A -->|"SQL"| DB
        DB --- V
    end

    B -->|"HTTPS"| I

    classDef web fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A
    classDef backend fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95
    classDef storage fill:#DCFCE7,stroke:#16A34A,color:#14532D

    class B,I,F web
    class G,P,T,A backend
    class DB,V storage
```

## References

- [Frontend HTTP client](../../../src/cofrap/frontend/openfaas_client.py)
- [OpenFaaS function definitions](../../../stack.yml)
- [Traefik entry point](../../../deploy/frontend-ingress.yaml)
- [Frontend deployment](../../../deploy/frontend.yaml)
- [PostgreSQL deployment](../../../deploy/postgres.yaml)
- [Detailed architecture](../architecture.md)
