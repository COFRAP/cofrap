# API HTTP

Cette page décrit l’API publique du frontend et les routes internes des fonctions.

## API JSON du frontend

La documentation interactive est accessible sur [/docs](http://localhost:8000/docs)
en local ; le schéma OpenAPI est disponible sur `/openapi.json`.

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
| `GET /health/ready` | Vérifier les fonctions et PostgreSQL | Aucune |

L’inscription retourne `enrollment_token`, `delivery_url`, `delivery_qr` et
`expires_at`. Le fragment de `delivery_url` est le jeton du endpoint de remise.
Les QR sont des PNG en data URL. Le mot de passe n’apparaît que dans la réponse à
la remise, jamais dans celle de l’inscription.

La connexion retourne HTTP 200 avec `status=authenticated` et un jeton de session,
ou `status=renewal_required` et un jeton limité au renouvellement. Ce second cas
**n’autorise pas** `/api/me`. Les jetons d’activation, de renouvellement et de
session se transmettent via
`Authorization: Bearer …` et expirent côté serveur.

Les erreurs ont la forme `{"error":{"code":"…","message":"…"}}` :
401 pour un facteur / jeton invalide, 409 pour un login déjà pris ou une activation
incomplète, 422 pour les entrées invalides. Elles ne recopient pas les données d’entrée.
Les erreurs HTMX conservent le formulaire et sont affichées dans sa zone d’alerte.

## Contrat HTTP des fonctions

Ces routes sont internes, préfixées par `/function/<nom>` sur la passerelle.
Toutes les opérations ci-dessous sont des POST avec un corps JSON.
Ces routes sont appelées par le frontend via la passerelle OpenFaaS.

| Fonction | Route | Entrée | Résultat |
| --- | --- | --- | --- |
| generate-password | `/register` | `username` | Compte, jetons, lien et QR de remise |
| generate-password | `/redeem` | `token` de remise | Mot de passe, une seule fois |
| generate-password | `/inspect` | `token` d’activation | Compte et état de remise |
| generate-password | `/qr` | `token` de remise | Lien et QR, sans vérifier sa validité en base ni le consommer |
| generate-password | `/renew` | `token` de renouvellement | Nouveau parcours d’activation |
| generate-2fa | `/setup` | `token` d’activation | Secret, URI TOTP et QR |
| generate-2fa | `/confirm` | `token` d’activation, `code` | Compte activé |
| authenticate | `/login` | `username`, `password`, `code` | Session ou `renewal_required` |
| authenticate | `/me` | `token` de session | Compte |
| authenticate | `/logout` | `token` de session | HTTP 204 |

Les fonctions valident les entrées. Les erreurs métier ont la forme
`{"error":{"code":"…","message":"…"}}`. Le frontend renvoie HTTP 503 si le
backend est indisponible, sans relancer automatiquement les appels.

