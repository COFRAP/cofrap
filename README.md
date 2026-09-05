# COFRAP — Identité sécurisée

PoC Python 3.12+, FastAPI, Pydantic, PostgreSQL et HTMX. Le navigateur appelle
l’application FastAPI ; les règles métier restent indépendantes du framework.
Le déploiement Kubernetes / OpenFaaS ne fait pas partie de cette implémentation.

## Architecture

```text
src/cofrap/
├── domain/          # Entités, règles, erreurs ; aucune dépendance web ou SQL
├── application/     # Cas d’usage et interfaces des adaptateurs
├── infrastructure/  # PostgreSQL, chiffrement, TOTP, configuration
└── presentation/    # Routes JSON / HTML, schémas Pydantic, templates HTMX
```

Les routes valident les entrées et présentent les résultats. Les cas d’usage
orchestrent le domaine via des interfaces. Les adaptateurs implémentent ces
interfaces. Une transaction couvre chaque opération métier.

## Développement

Les commandes de démarrage et les détails des parcours seront ajoutés au fil
des étapes de développement. Les secrets locaux ne doivent jamais être commités.
