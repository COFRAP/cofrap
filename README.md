# COFRAP — Identité sécurisée

Prototype d’authentification avec mot de passe généré, remise unique par QR code,
activation TOTP et renouvellement des identifiants après six mois.

Le projet utilise **trois fonctions OpenFaaS Python**, **PostgreSQL** et un
frontend **FastAPI / HTMX / Jinja2**.

## Démarrage rapide

Prérequis : Python 3.12+, Docker avec Compose et `make`.
Depuis la racine du projet :

```sh
make setup
make functions-up
```

Ouvrir **[l’application](http://localhost:8000)** ou la
[documentation interactive de l’API](http://localhost:8000/docs).

Le démarrage prépare `.env`, lance PostgreSQL, les migrations, les fonctions et
le frontend. En local, Nginx remplace la passerelle OpenFaaS.
Pour arrêter les conteneurs en conservant les données : `make functions-down`.

## Documentation

| Guide | Contenu |
| --- | --- |
| [Architecture](docs/architecture.md) | Composants, parcours utilisateur, sécurité et limites |
| [Base de données](docs/base-de-donnees.md) | Rôle de chaque colonne, types, jetons et durées de validité |
| [Développement local](docs/developpement.md) | Docker, configuration locale et tests |
| [API HTTP](docs/api.md) | Routes publiques et appels internes aux fonctions |
| [OpenFaaS](docs/openfaas.md) | Images, secrets et déploiement sur k3s |

## English

COFRAP is an authentication prototype with a generated password, one-time password
delivery through a QR code, TOTP setup, and credential renewal after six months.
It uses three Python OpenFaaS functions, PostgreSQL, and a FastAPI / HTMX / Jinja2 frontend.

Read the [English documentation and quick start](docs/en/README.md).

| Guide | Contents |
| --- | --- |
| [Architecture](docs/en/architecture.md) | Components, user flow, security, and limits |
| [Database](docs/en/database.md) | Columns, data types, tokens, and expiry times |
| [Local development](docs/en/development.md) | Docker, local settings, and tests |
| [HTTP API](docs/en/api.md) | Public routes and internal function calls |
| [OpenFaaS](docs/en/openfaas.md) | Images, secrets, and deployment on k3s |
| [System diagram](docs/en/diagrams/system-architecture.md) | Request flow and application components |
| [k3s cluster diagram](docs/en/diagrams/k3s-cluster-architecture.md) | Three machines and cluster services |
| [Bundled library](docs/en/third-party.md) | HTMX source and license |
