# COFRAP — Identité sécurisée

Backend **FastAPI / Pydantic**, persistance **PostgreSQL sous Docker**, interface
**HTMX / Jinja2** servie par Python. Le PoC couvre l’inscription, la remise unique
du mot de passe, l’activation TOTP, la connexion et le renouvellement après six mois.

## Démarrage local

Prérequis : Python 3.12+, Docker avec Compose, `make` facultatif.

```sh
make setup
make db
make migrate
make dev
```

Ouvrir **http://localhost:8000**. Documentation interactive de l’API :
**http://localhost:8000/docs** ; schéma OpenAPI : `/openapi.json`.

Sans `make` :

```sh
python3 -m venv .venv
.venv/bin/pip install -c requirements.lock -e '.[dev]'
.venv/bin/python scripts/init_env.py
docker compose up -d --wait postgres
.venv/bin/alembic upgrade head
.venv/bin/uvicorn cofrap.main:app --reload --host 127.0.0.1 --port 8000
```

`init_env.py` crée `.env` avec des secrets aléatoires et des permissions `0600`,
sans remplacer un fichier existant. Ne jamais commiter `.env`. Les versions Python
vérifiées sont fixées dans `requirements.lock`.

PostgreSQL est publié sur **127.0.0.1:55432**, avec le volume persistant
`cofrap_postgres_data`. `docker compose stop postgres` et `docker compose down`
conservent les données ; ajouter `-v` les détruit. Les migrations sont explicites,
jamais lancées automatiquement au démarrage de l’API.

## Essayer le parcours

1. Créer un nom d’utilisateur depuis l’accueil ; il est normalisé en minuscules.
2. Scanner le QR de remise ou cliquer sur **Révéler le mot de passe ici**.
   Enregistrer les 24 caractères dans un gestionnaire : la remise est unique.
3. Configurer le second QR dans une application TOTP. Une clé textuelle est
   disponible dans « Configurer sans scanner le QR ».
4. Saisir un code valide pour activer le compte. Aucun accès n’est possible avant.
5. Attendre le **prochain code de 30 secondes**, puis se connecter avec les deux facteurs.
6. Après six mois calendaires, les anciens facteurs autorisent uniquement le
   renouvellement. Le nouveau mot de passe et le nouveau TOTP doivent être configurés.

Le QR du mot de passe contient un lien temporaire, pas le mot de passe. L’ouverture
du lien ne consomme rien : seule une confirmation POST révèle le mot de passe.
Le QR TOTP configure l’application ; ce n’est pas un lien de remise unique.

Pour un téléphone, `localhost` désigne le téléphone : définir
`PUBLIC_BASE_URL=http://IP_DU_POSTE:8000` dans `.env`, redémarrer avec `--host 0.0.0.0`,
et ouvrir **cette même adresse** sur le poste et le téléphone, sur un réseau de confiance.
La base reste limitée à loopback. Utiliser HTTPS et `COOKIE_SECURE=true` dès que
l’application sort du développement local.

## Architecture

```text
src/cofrap/
├── domain/          # Entités, règles, erreurs ; aucune dépendance web ou SQL
├── application/     # Cas d’usage et interfaces des adaptateurs
├── infrastructure/  # PostgreSQL, chiffrement, TOTP, configuration
├── presentation/    # Routes JSON / HTML, schémas Pydantic, templates HTMX
└── main.py          # Assemblage des dépendances et cycle de vie de l’application
```

Les routes valident les entrées et présentent les résultats. Les cas d’usage
orchestrent le domaine via des interfaces. Les adaptateurs implémentent ces
interfaces. Les routes JSON et HTML partagent les mêmes services. Une transaction
couvre chaque opération métier, avec verrouillage des lignes pour la remise unique
et le rejet des codes TOTP rejoués. La contrainte unique PostgreSQL arbitre les
créations concurrentes. HTMX est servi localement et ne contient aucune règle métier.

Voir [l’architecture et les choix de sécurité](docs/architecture.md).

## API JSON

| Méthode et route | Usage | Autorisation |
| --- | --- | --- |
| `POST /api/users` | Créer le compte et le mot de passe | `username` |
| `POST /api/password-deliveries/redeem` | Consommer la remise | `token` dans le JSON |
| `POST /api/enrollment/totp` | Configurer le TOTP | Bearer d’activation |
| `POST /api/enrollment/confirm` | Confirmer et activer | Bearer d’activation + `code` |
| `POST /api/auth/login` | Connexion ou renouvellement requis | `username`, `password`, `code` |
| `POST /api/credentials/renew` | Remplacer les deux facteurs | Bearer de renouvellement |
| `GET /api/me` | Lire son compte | Bearer de session |
| `POST /api/auth/logout` | Révoquer la session | Bearer de session |
| `GET /health/live` | Vérifier le processus | Aucune |
| `GET /health/ready` | Vérifier la table utilisateurs | Aucune |

L’inscription retourne `enrollment_token`, `delivery_url`, `delivery_qr` et
`expires_at`. Le fragment de `delivery_url` est le jeton du endpoint de remise.
Les QR sont des PNG en data URL. Le mot de passe n’apparaît que dans la réponse à
la remise, jamais dans celle de l’inscription.

La connexion retourne HTTP 200 avec `status=authenticated` et un jeton de session,
ou `status=renewal_required` et un jeton limité au renouvellement. Ce second cas
**n’autorise pas** `/api/me`. Les jetons se transmettent via
`Authorization: Bearer …` et expirent côté serveur.

Les erreurs ont la forme `{"error":{"code":"…","message":"…"}}` :
401 pour un facteur / jeton invalide, 409 pour un login déjà pris ou une activation
incomplète, 422 pour les entrées invalides. Elles ne recopient pas les données d’entrée.
Les erreurs HTMX conservent le formulaire et sont affichées dans sa zone d’alerte.

## Vérification

```sh
make check                # Ruff + tests unitaires, sans base
make test-integration     # PostgreSQL temporaire sur 55433 + tous les tests
```

La base `cofrap_test` est distincte du développement, stockée en mémoire via `tmpfs`.
Les tests vident uniquement cette base et appliquent les vraies migrations.
`pytest` sans `--integration` ignore explicitement les tests PostgreSQL.

La suite couvre les mots de passe, le chiffrement, le TOTP, la remise concurrente,
les comptes inactifs, les collisions de login, les autorisations distinctes, les
frontières d’expiration, le renouvellement, la déconnexion, HTMX et CSRF.
L’horloge injectable simule l’expiration sans endpoint de falsification des dates.

## Limites du PoC

- Livraison limitée au backend, PostgreSQL et HTMX ; OpenFaaS / Kubernetes et les
  livrables de gestion de projet restent en dehors de cette étape.
- Une session par compte ; une nouvelle connexion remplace la précédente.
  Le navigateur conserve un seul parcours d’activation à la fois.
- Activation / remise : **15 minutes** ; renouvellement : **5 minutes** ;
  session : **30 minutes**, bornée par la validité des identifiants.
- Remise perdue, activation abandonnée ou facteur perdu : procédure assistée
  hors PoC. Aucun reset public n’est autorisé avec le seul login.
- Une TTL refuse l’accès mais ne supprime pas physiquement les chiffrés temporaires.
  La [commande de maintenance](docs/architecture.md#maintenance-locale) les purge.
- Limitation de débit, anti-spam, récupération assistée, sauvegardes et rotation
  des clés restent à prévoir avant exposition publique.
- Conserver la clé Fernet : sa perte empêche de déchiffrer les TOTP.
  Changer le mot de passe dans `.env` ne change pas celui d’un volume déjà initialisé.
