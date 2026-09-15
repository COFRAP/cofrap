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

## Déploiement sur k3s multi-nœuds

Le déploiement cible un serveur k3s et un ou plusieurs agents. Le PoC utilise
OpenFaaS Community gratuit, installé dans `openfaas` et `openfaas-fn` selon le
[guide Kubernetes officiel](https://docs.openfaas.com/deployment/kubernetes/).
Le scale-to-zero natif est exclu du PoC pour conserver cette édition gratuite ;
la justification et l’évolution possible sont décrites plus bas.
Le frontend est isolé dans le namespace `cofrap` et exposé par l’Ingress Traefik
fourni par défaut avec k3s.

Prérequis :

- `kubectl`, `faas-cli`, Docker/BuildKit et Kustomize sur la machine de construction ;
- tous les nœuds k3s en état `Ready` et à l’heure ;
- un registre HTTPS résolu et joignable par la machine de construction et chaque nœud ;
- un nom DNS public dirigé vers Traefik et un certificat TLS correspondant ;
- une classe de stockage choisie et une stratégie de sauvegarde PostgreSQL ;
- des images multi-architectures si les nœuds mélangent `amd64` et `arm64`.

```sh
kubectl get nodes -o wide
kubectl wait --for=condition=Ready node --all --timeout=180s
kubectl -n openfaas rollout status deployment/gateway
```

### Registre partagé

Les tags `local` et `latest` sont interdits pour le cluster. Utiliser un identifiant
immuable, par exemple le SHA Git. Chaque pod peut être planifié sur un nœud différent ;
charger une image dans le cache d’un seul nœud n’est donc pas un déploiement valide.

Pour un registre privé, configurer `/etc/rancher/k3s/registries.yaml` sur le serveur
et sur **chaque agent**. Exemple :

```yaml
mirrors:
  registry.example.com:
    endpoint:
      - https://registry.example.com
configs:
  registry.example.com:
    auth:
      username: REGISTRY_USER
      password: REGISTRY_PASSWORD
    tls:
      ca_file: /etc/rancher/k3s/registry-ca.crt
```

Protéger ce fichier, installer la CA sur tous les nœuds, puis redémarrer `k3s` sur
le serveur et `k3s-agent` sur les agents. Un registre public ne nécessite pas cette
configuration. Ne pas utiliser de registre HTTP non chiffré en production.

### Construction et publication

La passerelle peut rester privée. Le port-forward suivant est uniquement un tunnel
d’administration pour `faas-cli`, pas le point d’entrée des utilisateurs :

```sh
kubectl -n openfaas port-forward svc/gateway 8080:8080
```

Dans un autre terminal, se connecter à OpenFaaS et au registre, puis publier les
quatre images avec le même tag :

```sh
export OPENFAAS_URL=http://127.0.0.1:8080
export OPENFAAS_PREFIX=registry.example.com/cofrap
export IMAGE_TAG="$(git rev-parse --short=12 HEAD)"
export PUBLIC_BASE_URL=https://cofrap.example.com

docker login registry.example.com
faas-cli build -f stack.yml
faas-cli push -f stack.yml
docker build --target frontend \
  -t "${OPENFAAS_PREFIX}/cofrap-frontend:${IMAGE_TAG}" .
docker push "${OPENFAAS_PREFIX}/cofrap-frontend:${IMAGE_TAG}"
```

Une construction locale produit l’architecture de la machine. Pour un cluster mixte,
publier un manifeste multi-architecture pour chacune des quatre images avec la chaîne
BuildKit de l’organisation avant le déploiement.

### Configuration des manifests

Dans `deploy/kustomization.yaml`, remplacer `registry.example.com/cofrap` et
`replace-with-git-sha` par `OPENFAAS_PREFIX` et `IMAGE_TAG`. Dans
`deploy/deployment-config.yaml`, définir :

- `PUBLIC_BASE_URL`, origine HTTPS publique complète, sans chemin ;
- `COFRAP_HOST`, nom DNS seul utilisé par l’Ingress ;
- `STORAGE_CLASS`, classe CSI retenue pour PostgreSQL.

La valeur k3s `local-path` fonctionne sur un cluster standard mais attache les données
au disque d’un seul nœud. Une panne de ce nœud rend la base indisponible. Pour une
replanification sur un autre nœud, utiliser une classe CSI répliquée telle que Longhorn
ou une base PostgreSQL externe. Le StatefulSet fourni reste mono-instance dans tous
les cas et les sauvegardes doivent être organisées séparément.

Créer le secret TLS dans le namespace du frontend, sauf si cert-manager le gère :

```sh
kubectl create namespace cofrap --dry-run=client -o yaml | kubectl apply -f -
kubectl -n cofrap create secret tls cofrap-tls \
  --cert=/chemin/prive/tls.crt \
  --key=/chemin/prive/tls.key
```

Vérifier le rendu avant toute application. Les images finales ne doivent contenir
ni `replace-with-git-sha`, ni un registre d’exemple :

```sh
kubectl kustomize deploy > /tmp/cofrap-k3s.yaml
kubectl apply --dry-run=server -f /tmp/cofrap-k3s.yaml
```

### Secrets et déploiement

Dans le terminal de déploiement, exporter à nouveau `OPENFAAS_URL`,
`OPENFAAS_PREFIX`, `IMAGE_TAG` et `PUBLIC_BASE_URL` si celui de la construction
a été fermé. `faas-cli` substitue ces variables dans `stack.yml` ; il ne lit pas
les valeurs de `deploy/kustomization.yaml` ni de `deploy/deployment-config.yaml`.
Le registre et le tag doivent correspondre aux images publiées et à la migration,
et l’URL publique à celle du frontend. Les guillemets du YAML ne remplacent pas
ces valeurs obligatoires. Vérifier les images et les URL avant de déployer :

```sh
faas-cli generate -f stack.yml
```

Créer deux secrets OpenFaaS à partir de fichiers contenant uniquement leur valeur :
mot de passe PostgreSQL et clé Fernet. Conserver la même clé pour les trois fonctions,
la sauvegarder dans un coffre et garder ces fichiers hors Git.

```sh
faas-cli secret create cofrap-postgres-password --from-file /chemin/prive/postgres-password
faas-cli secret create cofrap-encryption-key --from-file /chemin/prive/encryption-key
```

Ils sont créés dans `openfaas-fn` et montés dans `/var/openfaas/secrets/`. Les
fonctions et le Job de migration les lisent à cet emplacement. Le frontend ne reçoit
aucun de ces secrets. Remplacer directement la clé Fernet rendrait les TOTP existants
illisibles. Changer le Secret PostgreSQL ne change pas le mot de passe d’une base déjà
initialisée.

Appliquer la base seule, attendre qu’elle soit prête, puis appliquer le rendu k3s.
Supprimer le Job terminé garantit que les migrations de la version courante sont
réellement rejouées. Le Job utilise exactement l’image `generate-password` publiée
avec les fonctions.

Les conteneurs de migration et du frontend utilisent explicitement l’UID `10001`,
celui de l’utilisateur `app` dans le Dockerfile. Kubernetes peut ainsi vérifier
`runAsNonRoot`, y compris avec les anciennes images qui déclarent `USER app`.
Après une modification du Job, le supprimer puis le recréer avec les commandes
ci-dessous : son template de pod est immuable. Cela vaut aussi pour un Job bloqué
en `CreateContainerConfigError`.

```sh
kubectl apply -k deploy --selector app=cofrap-postgres
kubectl -n openfaas-fn rollout status statefulset/postgres --timeout=180s
kubectl -n openfaas-fn get pvc

kubectl -n openfaas-fn delete job cofrap-migrate --ignore-not-found
kubectl apply -k deploy
kubectl -n openfaas-fn wait \
  --for=condition=complete job/cofrap-migrate --timeout=180s

faas-cli deploy -f stack.yml
kubectl -n openfaas-fn rollout status deployment/generate-password --timeout=180s
kubectl -n openfaas-fn rollout status deployment/generate-2fa --timeout=180s
kubectl -n openfaas-fn rollout status deployment/authenticate --timeout=180s
kubectl -n cofrap rollout status deployment/cofrap-frontend --timeout=180s
```

Contrôler ensuite les images, le placement sur les nœuds, l’Ingress et les probes :

```sh
kubectl get pods -A -o wide
kubectl -n openfaas-fn get deploy,pods -o wide
kubectl -n cofrap get deploy,pods,service,ingress,pdb -o wide
curl --fail https://cofrap.example.com/health/live
curl --fail https://cofrap.example.com/health/ready
```

Supprimer un pod de fonction et vérifier qu’il redémarre sur un agent sans
`ImagePullBackOff`. Cette vérification valide l’accès au registre depuis les nœuds,
contrairement à un simple test depuis la machine de construction.

## Scale to Zero

### Pourquoi il est absent du PoC

Le scale-to-zero arrête les réplicas d’une fonction après une période sans trafic
et les recrée à la première requête. Cette fonctionnalité native nécessite
OpenFaaS Standard/Pro avec une licence et son autoscaler. Le PoC conserve
OpenFaaS Community gratuit : le scale-to-zero n’est donc pas implémenté.
Voir le
[guide officiel Scale to Zero](https://docs.openfaas.com/openfaas-pro/scale-to-zero/).

Sur le cluster du PoC, la passerelle refuse le déploiement avec l’erreur :

```text
validation failed: com.openfaas.scale.zero not available for Community Edition
```

Les labels `com.openfaas.scale.zero` et `com.openfaas.scale.zero-duration` sont
donc absents de `stack.yml`. Chaque fonction conserve au moins un réplica
(`com.openfaas.scale.min: "1"`), même sans trafic, et continue de consommer des
ressources. Le frontend et PostgreSQL restent également actifs. Aucun composant
externe de mise à zéro n’est installé dans le PoC.

### Évolution possible avec Standard/Pro

Après installation d’une édition compatible et de son autoscaler avec
`autoscaler.enabled: true`, ajouter aux labels de chacune des trois fonctions :

```yaml
com.openfaas.scale.zero: "true"
com.openfaas.scale.zero-duration: "10m"
```

Le minimum de `1` correspond alors au nombre de réplicas actifs après réveil.
Les fonctions ne conservent aucun état utilisateur en mémoire ; leurs pools SQL
sont recréés au redémarrage. `OPENFAAS_TIMEOUT=60` laisse une marge au démarrage
à froid, à valider sur le cluster équipé.

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
Elle ne valide pas non plus le registre, le placement multi-nœuds, l’Ingress TLS,
la reprise du volume PostgreSQL ni la réaction à la perte d’un nœud.

Le parcours et le stockage existants sont conservés : QR de récupération à usage
unique, hachage Argon2 permanent, chiffrement temporaire du mot de passe et
expiration six mois après activation. Les différences d’interprétation du cahier
des charges sont détaillées dans `architecture.md`.

Références : [Dockerfile OpenFaaS](https://docs.openfaas.com/languages/dockerfile/),
[of-watchdog](https://github.com/openfaas/of-watchdog),
[stack.yml](https://docs.openfaas.com/reference/yaml/).
