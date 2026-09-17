# OpenFaaS

Cette page explique comment les fonctions COFRAP sont exécutées et déployées
avec OpenFaaS Community sur k3s.

## Les trois fonctions

| Fonction | Rôle |
| --- | --- |
| `generate-password` | Inscription, remise unique du mot de passe et renouvellement |
| `generate-2fa` | Configuration TOTP et activation du compte |
| `authenticate` | Connexion, session et déconnexion |

Le frontend les appelle via la passerelle OpenFaaS. Elles partagent la même base
PostgreSQL. Le détail des routes est dans [la documentation API](api.md#contrat-http-des-fonctions).

## Images des fonctions

Chaque fonction possède sa propre image. Le [Dockerfile](../Dockerfile) commun
sélectionne son dossier avec `FUNCTION_NAME` et installe le package `src/cofrap`.
Les dépendances communes viennent de `pyproject.toml`, avec les versions fixées
par `requirements.lock`. Les `requirements.txt` des fonctions sont réservés aux
dépendances supplémentaires ; ils ne contiennent actuellement que des commentaires.

Chaque image exécute FastAPI derrière `of-watchdog` en mode HTTP. Le binaire
est fixé à la version 0.11.9, vérifié par SHA-256 et disponible pour `amd64` et
`arm64`. [stack.yml](../stack.yml) définit les images, variables, secrets et
limites de ressources des trois fonctions.

## Déploiement sur k3s multi-nœuds

Le dossier [deploy/](../deploy/) fournit PostgreSQL, la migration et le frontend.
Les trois fonctions sont déployées séparément avec [stack.yml](../stack.yml).

Prérequis : un cluster k3s prêt avec Traefik et OpenFaaS Community déjà installé
(namespaces `openfaas` et `openfaas-fn`), Docker/BuildKit, `kubectl`, `faas-cli`,
un registre accessible par tous les nœuds et un nom DNS avec certificat TLS.
Pour un registre privé, configurer l’accès sur chaque nœud k3s.

### 1. Publier les images

Ouvrir un tunnel vers la passerelle dans un terminal dédié :

```sh
kubectl -n openfaas port-forward svc/gateway 8080:8080
```

Le port 8080 doit être libre : arrêter la passerelle Docker locale si nécessaire.
Dans un autre terminal, adapter les valeurs puis se connecter :

```sh
export OPENFAAS_URL=http://127.0.0.1:8080
export OPENFAAS_PREFIX=registry.example.com/cofrap
export IMAGE_TAG="$(git rev-parse --short=12 HEAD)"
export PUBLIC_BASE_URL=https://cofrap.example.com

faas-cli login
docker login registry.example.com
faas-cli build -f stack.yml
faas-cli push -f stack.yml
docker build --target frontend \
  -t "${OPENFAAS_PREFIX}/cofrap-frontend:${IMAGE_TAG}" .
docker push "${OPENFAAS_PREFIX}/cofrap-frontend:${IMAGE_TAG}"
```

Utiliser un tag propre à la version publiée. La construction locale cible
l’architecture de la machine ; un cluster mélangeant `amd64` et `arm64` nécessite
des images multi-architectures pour les quatre composants.

### 2. Adapter la configuration

Dans [deploy/kustomization.yaml](../deploy/kustomization.yaml), adapter les champs
`newName` et `newTag` des images de migration (`cofrap-generate-password`) et du
frontend. Ils doivent correspondre au registre et au tag publiés à l’étape 1.
Les valeurs déjà présentes dans ce fichier ne sont pas remplacées automatiquement.

Dans [deploy/deployment-config.yaml](../deploy/deployment-config.yaml), définir :

| Clé | Valeur attendue |
| --- | --- |
| `PUBLIC_BASE_URL` | Origine HTTPS publique, identique à la variable exportée |
| `COFRAP_HOST` | Nom DNS seul, pour l’Ingress |
| `STORAGE_CLASS` | Classe de stockage PostgreSQL |

Le frontend utilise deux réplicas, `COOKIE_SECURE=true` et une redirection HTTPS.
La répartition sur plusieurs nœuds est préférée, pas imposée. PostgreSQL reste
mono-instance ; avec `local-path`, ses données dépendent du disque d’un seul nœud.
Les sauvegardes et la reprise après panne restent à organiser.

Créer le namespace et le certificat (sauf si celui-ci est géré par cert-manager) :

```sh
kubectl create namespace cofrap --dry-run=client -o yaml | kubectl apply -f -
kubectl -n cofrap create secret tls cofrap-tls \
  --cert=/chemin/prive/tls.crt --key=/chemin/prive/tls.key
```

### 3. Créer les secrets

Préparer hors Git deux fichiers contenant respectivement le mot de passe
PostgreSQL et une clé Fernet valide, puis créer les secrets OpenFaaS :

```sh
faas-cli secret create cofrap-postgres-password --from-file /chemin/prive/postgres-password
faas-cli secret create cofrap-encryption-key --from-file /chemin/prive/encryption-key
```

Les fonctions et la migration lisent ces secrets sous `/var/openfaas/secrets/`.
Le frontend ne les reçoit pas. Conserver la clé Fernet : son remplacement rendrait
les secrets TOTP existants illisibles. Modifier le secret PostgreSQL ne change pas
le mot de passe d’une base déjà initialisée.

### 4. Appliquer et vérifier

Garder les quatre variables de l’étape 1 dans ce terminal : `faas-cli` les utilise
pour `stack.yml`, indépendamment des fichiers Kustomize. Vérifier le rendu :

```sh
faas-cli generate -f stack.yml
kubectl kustomize deploy > /tmp/cofrap-k3s.yaml
kubectl apply --dry-run=server -f /tmp/cofrap-k3s.yaml
```

Démarrer la base, appliquer les ressources, attendre la migration puis déployer
les fonctions. Lors d’une mise à jour, supprimer le précédent Job de migration
une fois terminé pour exécuter celui de la nouvelle version :

```sh
kubectl apply -k deploy --selector app=cofrap-postgres
kubectl -n openfaas-fn rollout status statefulset/postgres --timeout=180s
kubectl -n openfaas-fn delete job cofrap-migrate --ignore-not-found
kubectl apply -k deploy
kubectl -n openfaas-fn wait --for=condition=complete job/cofrap-migrate --timeout=180s
faas-cli deploy -f stack.yml

kubectl -n openfaas-fn rollout status deployment/generate-password --timeout=180s
kubectl -n openfaas-fn rollout status deployment/generate-2fa --timeout=180s
kubectl -n openfaas-fn rollout status deployment/authenticate --timeout=180s
kubectl -n cofrap rollout status deployment/cofrap-frontend --timeout=180s
kubectl get pods -A -o wide
curl --fail "${PUBLIC_BASE_URL}/health/live"
curl --fail "${PUBLIC_BASE_URL}/health/ready"
```

`/health/live` vérifie uniquement le frontend ; les probes Kubernetes utilisent
cette route. `/health/ready` appelle les trois fonctions et vérifie leur accès à
la table `users` dans PostgreSQL.

## Scale to Zero

Le PoC ne met pas les fonctions à zéro en l’absence de trafic. `stack.yml` fixe
un minimum de 1 réplica et un maximum de 3 par fonction, sans label de mise à zéro.
Le frontend et PostgreSQL restent également actifs.

Le [guide officiel OpenFaaS](https://docs.openfaas.com/openfaas-pro/scale-to-zero/)
décrit cette fonctionnalité avec OpenFaaS Pro et son autoscaler. Elle n’est pas
configurée dans ce projet, qui cible Community.

## Vérifications et limites

`make test-integration` vérifie les applications des fonctions, le frontend et
PostgreSQL via un transport HTTP de test. Il ne valide ni le watchdog, ni Nginx,
ni Kubernetes. Sur le cluster cible, il reste à vérifier le parcours utilisateur,
TLS, l’accès au registre depuis chaque nœud et la reprise après une panne.

Les règles d’activation, de stockage et d’expiration sont décrites dans
[architecture.md](architecture.md).
