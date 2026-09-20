# COFRAP k3s cluster architecture

```mermaid
flowchart TB
    U["Users"]

    subgraph CLUSTER["COFRAP — Three-machine k3s cluster"]
        subgraph INFRA["Infrastructure"]
            S["COFRAP-K3S-SERVER<br/>k3s cluster control<br/>API and orchestration"]
            A1["COFRAP-K3S-AGENT-1<br/>Worker node<br/>Runs applications"]
            A2["COFRAP-K3S-AGENT-2<br/>Worker node<br/>Runs applications"]
            S -.->|"Orchestration"| A1
            S -.->|"Orchestration"| A2
        end

        subgraph APP["Cluster application services"]
            E["Traefik<br/>Web entry point"]
            F["COFRAP application<br/>Web interface · 2 replicas"]
            O["OpenFaaS<br/>Gateway and 3 business functions<br/>Password · Second factor · Authentication"]
            D[("PostgreSQL<br/>1 instance and persistent storage")]
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

Solid lines show the request flow. Dotted lines show orchestration and where
applications run.

This view uses the three supplied machine names. Services are shown at cluster
level. The repository manifests do not require them to run on specific nodes,
and their actual placement has not been checked on the cluster. The k3s server
can also run pods, depending on its configuration.

The frontend has two replicas and prefers to spread them across nodes.
PostgreSQL has one instance. The default storage is `local-path`, tied to one node.

Sources: [frontend](../../../deploy/frontend.yaml),
[PostgreSQL](../../../deploy/postgres.yaml),
[OpenFaaS functions](../../../stack.yml),
[Traefik](../../../deploy/frontend-ingress.yaml).
