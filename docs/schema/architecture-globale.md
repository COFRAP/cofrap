# Architecture globale de COFRAP


```mermaid
flowchart LR
    B["Utilisateur<br/>Navigateur avec HTMX"]

    subgraph K3S["Cluster Kubernetes — k3s"]
        I["Entrée HTTPS<br/>Traefik"]
        F["Frontend · 2 réplicas<br/>FastAPI / Jinja2<br/>Pages HTML et API JSON"]
        G["Passerelle OpenFaaS<br/>Routage des appels"]

        subgraph FN["Fonctions Python — images indépendantes"]
            P["generate-password<br/>Inscription et renouvellement<br/>Remise unique du mot de passe"]
            T["generate-2fa<br/>Configuration TOTP<br/>Activation du compte"]
            A["authenticate<br/>Connexion avec mot de passe + TOTP<br/>Session et déconnexion"]
        end

        DB[("PostgreSQL 17<br/>Base commune · 1 instance")]
        V[("Volume persistant")]

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

## Références

- [Client HTTP du frontend](../../src/cofrap/frontend/openfaas_client.py)
- [Déclaration des fonctions OpenFaaS](../../stack.yml)
- [Entrée Traefik](../../deploy/frontend-ingress.yaml)
- [Déploiement du frontend](../../deploy/frontend.yaml)
- [Déploiement PostgreSQL](../../deploy/postgres.yaml)
- [Architecture détaillée](../architecture.md)

