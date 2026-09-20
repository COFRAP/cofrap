# Développement local

## Démarrer avec Docker

Prérequis : Python 3.12+, Docker avec Compose et `make`.
Depuis la racine du projet :

```sh
make setup
make functions-up
```

Ces commandes créent `.env` s’il n’existe pas, installent les dépendances et lancent :

- PostgreSQL sur `127.0.0.1:55432` et les migrations ;
- les trois fonctions avec le watchdog ;
- une passerelle Nginx sur `127.0.0.1:8080` ;
- le frontend sur **http://localhost:8000**.

Ce mode n’installe ni OpenFaaS ni Kubernetes. Pour modifier le frontend avec
rechargement automatique, garder les autres conteneurs actifs puis lancer :

```sh
docker compose -f compose.yaml -f compose.functions.yaml stop frontend
make dev
```

`OPENFAAS_GATEWAY_URL` indique la passerelle au frontend. `PUBLIC_BASE_URL` doit
être identique côté frontend et fonctions pour que les liens des QR soient corrects.
`make functions-down` arrête les conteneurs sans supprimer le volume PostgreSQL.

Pour un téléphone, `localhost` désigne le téléphone : définir
`PUBLIC_BASE_URL=http://IP_DU_POSTE:8000` dans `.env`, publier le port du frontend
sur cette interface dans `compose.functions.yaml`,
et ouvrir **cette même adresse** sur le poste et le téléphone, sur un réseau de confiance.
La base reste limitée à loopback. Utiliser HTTPS et `COOKIE_SECURE=true` dès que
l’application sort du développement local.

## Vérifier les changements

```sh
make check                # Style et tests unitaires
make test-integration     # Tests avec PostgreSQL dédié sur le port 55433
```

Voir les [limites des tests](architecture.md#vérification-et-limites).
Le déploiement sur un cluster est décrit dans [OpenFaaS](openfaas.md).

Les tests de `tests/unit/functions` appellent directement la logique métier des trois
fonctions OpenFaaS, sans HTTP, Docker ni PostgreSQL. Ils utilisent un stockage en
mémoire, une heure fixe et les vrais outils de chiffrement et de TOTP. Ils couvrent
les cas positifs et négatifs : inscription, remise unique du mot de passe, activation
2FA, connexion, déconnexion, expiration et renouvellement.

Pour lancer uniquement ces tests :

```sh
.venv/bin/pytest tests/unit/functions -q
```
