# Architecture globale du cluster COFRAP K3s

```mermaid
flowchart TB
    U["Utilisateurs"]

    subgraph CLUSTER["COFRAP — Cluster K3s à 3 machines"]
        subgraph INFRA["Infrastructure"]
            S["COFRAP-K3S-SERVER<br/>Pilotage du cluster K3s<br/>API et orchestration"]
            A1["COFRAP-K3S-AGENT-1<br/>Nœud de travail<br/>Exécution des applications"]
            A2["COFRAP-K3S-AGENT-2<br/>Nœud de travail<br/>Exécution des applications"]
            S -.->|"Orchestration"| A1
            S -.->|"Orchestration"| A2
        end

        subgraph APP["Services applicatifs du cluster"]
            E["Traefik<br/>Entrée web"]
            F["Application COFRAP<br/>Interface web · 2 réplicas"]
            O["OpenFaaS<br/>Passerelle et 3 fonctions métier<br/>Mot de passe · Double facteur · Authentification"]
            D[("PostgreSQL<br/>1 instance et stockage persistant")]
            E --> F --> O --> D
        end

        A1 -.-> APP
        A2 -.-> APP
    end

    U -->|"HTTPS"| E

    classDef control fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A
    classDef worker fill:#E0F2FE,stroke:#0284C7,color:#0C4A6E
    classDef app fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95
    classDef data fill:#DCFCE7,stroke:#16A34A,color:#14532D
    class S control
    class A1,A2 worker
    class E,F,O app
    class D data
    style CLUSTER fill:#F8FAFC,stroke:#64748B
    style INFRA fill:#EFF6FF,stroke:#93C5FD
    style APP fill:#FFFFFF,stroke:#C4B5FD
```

Les traits pleins représentent le parcours des requêtes. Les pointillés représentent l’orchestration et l’hébergement des applications.

Cette vue utilise les trois noms de machines fournis. Les services sont représentés à l’échelle du cluster : leur placement exact sur les nœuds n’est pas imposé par les manifestes du dépôt et n’a pas été vérifié sur le cluster. Le serveur K3s peut également exécuter des pods selon sa configuration.

Le frontend possède deux réplicas avec une préférence de répartition entre les nœuds. PostgreSQL possède une seule instance ; le stockage configuré par défaut est `local-path`, lié à un nœud.

Sources : [frontend](../../deploy/frontend.yaml), [PostgreSQL](../../deploy/postgres.yaml), [fonctions OpenFaaS](../../stack.yml), [Traefik](../../deploy/frontend-ingress.yaml).
