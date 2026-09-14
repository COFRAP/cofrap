# Fonctions OpenFaaS et déploiement

## Organisation

- `functions/generate-password/` : `handler.py` expose inscription, renouvellement,
  remise unique, consultation du parcours et affichage du QR ; `service.py` contient
  les transactions correspondantes.
- `functions/generate-2fa/` : génération du secret chiffré et du QR, puis confirmation
  du premier code pour activer le compte.
- `functions/authenticate/` : connexion, expiration à six mois, session et déconnexion.
- `src/cofrap/frontend/` : FastAPI, HTMX et client HTTP. Aucun accès direct à la base.
- `src/cofrap/domain/`, `application/`, `infrastructure/`, `contracts.py` et
  `function_runtime.py` : package commun installé dans chaque image.

Chaque fonction possède son `handler.py`, son `service.py`, son `requirements.txt`
et sa propre image. Le Dockerfile commun utilise `FUNCTION_NAME` pour copier uniquement
le dossier de la fonction concernée dans `/app/function`. Le contexte de construction
est la racine (`handler: .` dans `stack.yml`) pour inclure le package partagé.
Les dépendances communes restent dans `pyproject.toml` et `requirements.lock`.

Le Dockerfile télécharge le binaire officiel `of-watchdog` 0.11.9 depuis les
releases GitHub pour `amd64` ou `arm64`, avec vérification SHA-256 intégrée à
la construction. Aucun identifiant GHCR n’est nécessaire.

Le mode OpenFaaS `dockerfile` avec `of-watchdog` en mode HTTP permet de conserver
FastAPI/Pydantic dans chaque fonction. Il ne nécessite pas le template Flask
`python3-http`. Le frontend est un quatrième processus, avec sa propre image.

## Contrat HTTP

Les chemins ci-dessous sont préfixés par `/function/<nom-de-fonction>` sur la passerelle.
Tous les paramètres sensibles sont envoyés dans le corps JSON, jamais dans l’URL.

| Fonction | POST | Corps JSON | Résultat |
| --- | --- | --- | --- |
| generate-password | `/register` | `username` | utilisateur, jetons, lien et QR de remise |
| generate-password | `/redeem` | `token` de remise | mot de passe, une seule fois |
| generate-password | `/inspect` | `token` d’activation | utilisateur et état de remise |
| generate-password | `/qr` | `token` de remise | lien et QR, sans consommer le jeton |
| generate-password | `/renew` | `token` de renouvellement | nouveau parcours et QR |
| generate-2fa | `/setup` | `token` d’activation | secret, URI TOTP et QR |
| generate-2fa | `/confirm` | `token` d’activation, `code` | compte activé |
| authenticate | `/login` | `username`, `password`, `code` | session ou `renewal_required` |
| authenticate | `/me` | `token` de session | utilisateur |
| authenticate | `/logout` | `token` de session | HTTP 204 |

Chaque fonction valide ses propres entrées, même si elle est appelée directement.
Les erreurs métier conservent leur code HTTP et un objet `error` avec `code` et
`message`. Le frontend traduit les indisponibilités réseau en HTTP 503. Aucun
retry automatique n’est appliqué : une remise peut avoir été consommée avant
qu’une réponse réseau soit perdue.

## Exécution locale avec Docker

```sh
make setup
make functions-up
```

Cela lance PostgreSQL, un conteneur de migration, les trois images avec le watchdog,
une passerelle Nginx de développement sur `127.0.0.1:8080` et le frontend sur
`http://localhost:8000`. Ce mode vérifie la séparation HTTP mais n’installe pas
OpenFaaS/Kubernetes et ne fournit pas de scale-to-zero.

Pour travailler sur le frontend avec rechargement automatique :

```sh
docker compose -f compose.yaml -f compose.functions.yaml stop frontend
make dev
```

`OPENFAAS_GATEWAY_URL` désigne la passerelle. `PUBLIC_BASE_URL` doit être identique
côté frontend et fonctions pour que les QR pointent vers le bon navigateur.

## Déploiement sur Minikube

Prérequis : Docker, Minikube, kubectl, faas-cli et une installation OpenFaaS dans
les namespaces `openfaas` et `openfaas-fn`. Installer la plateforme selon le
[guide officiel](https://docs.openfaas.com/deployment/kubernetes/), après :

```sh
minikube start --driver=docker --cpus=4 --memory=6144
```

Pour des images chargées localement, configurer le fournisseur OpenFaaS avec
`faasnetes.imagePullPolicy=IfNotPresent` (valeur Helm). Sans cela, le fournisseur
peut tenter de télécharger les images locales depuis un registre.

Dans un terminal, exposer la passerelle :

```sh
kubectl -n openfaas port-forward svc/gateway 8080:8080
```

S’authentifier avec `faas-cli login` selon les instructions de l’installation.
Arrêter auparavant la passerelle Docker locale si elle occupe le port 8080.

Configurer et construire les images locales :

```sh
export OPENFAAS_URL=http://127.0.0.1:8080
export OPENFAAS_PREFIX=cofrap
export IMAGE_TAG=local
export PUBLIC_BASE_URL=http://localhost:8000
faas-cli build -f stack.yml
docker build --target frontend -t cofrap-frontend:local .
minikube image load cofrap/cofrap-generate-password:local
minikube image load cofrap/cofrap-generate-2fa:local
minikube image load cofrap/cofrap-authenticate:local
minikube image load cofrap-frontend:local
```

Créer deux secrets OpenFaaS à partir de fichiers locaux contenant uniquement leur
valeur : mot de passe PostgreSQL et clé Fernet. Conserver la même clé pour les trois
fonctions. Garder ces fichiers hors Git.

```sh
faas-cli secret create cofrap-postgres-password --from-file /chemin/prive/postgres-password
faas-cli secret create cofrap-encryption-key --from-file /chemin/prive/encryption-key
```

Ils sont montés dans `/var/openfaas/secrets/`. Les fonctions et le Job de migration
les lisent à cet emplacement. Le frontend ne reçoit aucun de ces secrets.

Démarrer la base puis appliquer les migrations avant de déployer les fonctions :

```sh
kubectl apply -f deploy/postgres.yaml
kubectl -n openfaas-fn rollout status statefulset/postgres
kubectl apply -f deploy/migrate.yaml
kubectl -n openfaas-fn wait --for=condition=complete job/cofrap-migrate --timeout=120s
faas-cli deploy -f stack.yml
kubectl apply -f deploy/frontend.yaml
kubectl -n openfaas rollout status deployment/cofrap-frontend
kubectl -n openfaas port-forward svc/cofrap-frontend 8000:8000
```

Pour une nouvelle version de migration, créer un Job avec un nouveau nom. Pour un
cluster distant, utiliser un registre accessible au cluster, publier les images
avec `faas-cli push` et adapter les images des manifests frontend/migration.

## Scale to Zero

`stack.yml` active les labels `com.openfaas.scale.zero` et
`com.openfaas.scale.zero-duration: 10m`. Leur effet nécessite une édition OpenFaaS
avec l’autoscaler approprié et `autoscaler.enabled: true` dans sa configuration
Helm ; les labels seuls ne suffisent pas. Voir le
[guide officiel Scale to Zero](https://docs.openfaas.com/openfaas-pro/scale-to-zero/).

Le frontend et PostgreSQL restent disponibles. Les fonctions ne conservent aucun
état utilisateur en mémoire ; leurs pools SQL sont recréés au redémarrage.
`OPENFAAS_TIMEOUT=60` laisse une marge au redémarrage d’une fonction.

Les probes Kubernetes du frontend utilisent `/health/live`. Ne pas sonder en
boucle son `/health/ready` : ce diagnostic appelle les trois fonctions, vérifie
PostgreSQL et les maintiendrait actives.

Pour vérifier le mécanisme sur un cluster équipé, observer les déploiements des
trois fonctions pendant plus de dix minutes sans requête, puis refaire une connexion.

## Vérifications et limites

`make test-integration` exécute les trois applications de fonction séparément
avec leur propre cycle de vie et leurs connexions PostgreSQL. Le client HTTP du
frontend traverse un transport de test qui route vers ces applications ; il ne
court-circuite pas les handlers. Cette suite ne valide pas Kubernetes ni le watchdog.

Le parcours et le stockage existants sont conservés : QR de récupération à usage
unique, hachage Argon2 permanent, chiffrement temporaire du mot de passe et
expiration six mois après activation. Les différences d’interprétation du cahier
des charges sont détaillées dans `architecture.md`.

Références : [Dockerfile OpenFaaS](https://docs.openfaas.com/languages/dockerfile/),
[of-watchdog](https://github.com/openfaas/of-watchdog),
[stack.yml](https://docs.openfaas.com/reference/yaml/).
