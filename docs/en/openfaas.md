# OpenFaaS

This page explains how COFRAP functions run and how to deploy them with OpenFaaS
Community on k3s.

## The three functions

| Function | Purpose |
| --- | --- |
| `generate-password` | Registration, one-time password delivery, and renewal |
| `generate-2fa` | TOTP setup and account activation |
| `authenticate` | Login, session, and logout |

The frontend calls them through the OpenFaaS gateway. They share the same
PostgreSQL database. See the [API guide](api.md#function-http-contract) for route details.

## Function images

Each function has its own image. The shared [Dockerfile](../../Dockerfile)
selects its folder with `FUNCTION_NAME` and installs the `src/cofrap` package.
Shared dependencies come from `pyproject.toml`, with versions pinned in
`requirements.lock`. Each function's `requirements.txt` is for extra dependencies.
These files currently contain only comments.

Each image runs FastAPI behind `of-watchdog` in HTTP mode. The binary is pinned
to version 0.11.9, checked with SHA-256, and available for `amd64` and `arm64`.
[stack.yml](../../stack.yml) defines images, variables, secrets, and resource
limits for the three functions.

## Deploy on a multi-node k3s cluster

The [deploy/](../../deploy/) folder provides PostgreSQL, the migration, and the
frontend. Deploy the three functions separately with [stack.yml](../../stack.yml).

Requirements: a ready k3s cluster with Traefik and OpenFaaS Community already
installed (namespaces `openfaas` and `openfaas-fn`), Docker/BuildKit, `kubectl`,
`faas-cli`, a registry that all nodes can reach, and a DNS name with a TLS
certificate. For a private registry, set up access on every k3s node.

### 1. Publish the images

Open a tunnel to the gateway in a separate terminal:

```sh
kubectl -n openfaas port-forward svc/gateway 8080:8080
```

Port 8080 must be free. Stop the local Docker gateway if needed.
In another terminal, adjust the values below, then log in:

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

Use a tag specific to the published version. Local builds target your machine's
architecture. A cluster with both `amd64` and `arm64` nodes needs multi-architecture
images for all four components.

### 2. Adjust the configuration

In [deploy/kustomization.yaml](../../deploy/kustomization.yaml), update `newName`
and `newTag` for the migration image (`cofrap-generate-password`) and the frontend
image. They must match the registry and tag published in step 1.
The existing values in this file are not replaced automatically.

In [deploy/deployment-config.yaml](../../deploy/deployment-config.yaml), set:

| Key | Expected value |
| --- | --- |
| `PUBLIC_BASE_URL` | Public HTTPS origin, matching the exported variable |
| `COFRAP_HOST` | DNS name only, for the Ingress |
| `STORAGE_CLASS` | PostgreSQL storage class |

The frontend uses two replicas, `COOKIE_SECURE=true`, and an HTTPS redirect.
Spreading replicas across nodes is preferred, not required. PostgreSQL remains
a single instance. With `local-path`, its data depends on one node's disk.
Backups and recovery after a failure still need to be set up.

Create the namespace and certificate (unless cert-manager manages the certificate):

```sh
kubectl create namespace cofrap --dry-run=client -o yaml | kubectl apply -f -
kubectl -n cofrap create secret tls cofrap-tls \
  --cert=/private/path/tls.crt --key=/private/path/tls.key
```

### 3. Create secrets

Prepare two files outside Git: one with the PostgreSQL password and one with a
valid Fernet key. Then create the OpenFaaS secrets:

```sh
faas-cli secret create cofrap-postgres-password --from-file /private/path/postgres-password
faas-cli secret create cofrap-encryption-key --from-file /private/path/encryption-key
```

The functions and migration read these secrets under `/var/openfaas/secrets/`.
The frontend does not receive them. Keep the Fernet key: replacing it would make
existing TOTP secrets unreadable. Changing the PostgreSQL secret does not change
the password of a database that has already been initialized.

### 4. Apply and check

Keep the four variables from step 1 in this terminal. `faas-cli` uses them for
`stack.yml`, separately from the Kustomize files. Check the generated configuration:

```sh
faas-cli generate -f stack.yml
kubectl kustomize deploy > /tmp/cofrap-k3s.yaml
kubectl apply --dry-run=server -f /tmp/cofrap-k3s.yaml
```

Start the database, apply the resources, wait for the migration, then deploy the
functions. During an update, delete the previous migration Job after it has
finished so that the new version's Job can run:

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

`/health/live` only checks the frontend. Kubernetes probes use this route.
`/health/ready` calls all three functions and checks their access to PostgreSQL's
`users` table.

## Scale to Zero

The prototype does not scale functions down to zero when there is no traffic.
`stack.yml` sets a minimum of 1 replica and a maximum of 3 per function, with no
scale-to-zero label. The frontend and PostgreSQL also stay running.

The [official OpenFaaS guide](https://docs.openfaas.com/openfaas-pro/scale-to-zero/)
describes this feature with OpenFaaS Pro and its autoscaler. It is not configured
in this project, which targets Community.

## Checks and limits

`make test-integration` checks the function apps, frontend, and PostgreSQL through
a test HTTP transport. It does not test the watchdog, Nginx, or Kubernetes.
On the target cluster, the user flow, TLS, registry access from every node, and
recovery after a failure still need to be checked.

See [architecture.md](architecture.md) for activation, storage, and expiry rules.
