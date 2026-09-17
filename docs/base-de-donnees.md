# Base de données — dictionnaire des colonnes

La base PostgreSQL contient une table métier, `users` : chaque ligne représente
un utilisateur, ses identifiants et ses jetons temporaires. Les jetons sont
stockés dans cette même ligne ; il n’existe pas de table de sessions séparée.
Alembic utilise également une table technique, `alembic_version`, pour suivre
les migrations appliquées.

Cette documentation décrit le [schéma initial](../migrations/versions/0001_create_users.py)
et le [modèle SQLAlchemy](../src/cofrap/infrastructure/database.py).

## Comment lire les valeurs

- **NULL autorisé** : la colonne peut ne contenir aucune valeur. Cela indique
  généralement une étape non réalisée, un jeton absent ou une donnée effacée.
- **Empreinte / hachage** : résultat permettant de vérifier une valeur sans
  conserver sa version originale. Les mots de passe utilisent Argon2id ; les
  jetons utilisent SHA-256, sous forme de 64 caractères hexadécimaux.
- **Chiffrement** : protection réversible avec la clé de l’application. Fernet
  permet de retrouver le mot de passe avant sa remise et le secret TOTP pour
  vérifier les codes.
- Les dates utilisent le type PostgreSQL `TIMESTAMP WITH TIME ZONE`
  (`TIMESTAMPTZ`). L’application effectue ses calculs en UTC.

## Table `users` : les 18 colonnes

### Identité et mot de passe

| Colonne | Type PostgreSQL | NULL autorisé | Explication |
| --- | --- | --- | --- |
| `id` | `UUID` | Non | Identifiant interne unique de l’utilisateur, généré par l’application avec UUID v4 à l’inscription. Clé primaire, conservée lors du renouvellement. |
| `username` | `VARCHAR(64)` | Non | Nom de connexion de l’utilisateur. Une contrainte d’unicité empêche deux comptes d’avoir le même nom enregistré. |
| `password_hash` | `TEXT` | Non | Hachage Argon2id du mot de passe généré. Sert à vérifier le mot de passe à la connexion sans le déchiffrer. Remplacé lors du renouvellement. |
| `created_at` | `TIMESTAMPTZ` | Non | Date de création du compte. Elle reste inchangée lors des activations et renouvellements. |

### Activation, validité et second facteur

| Colonne | Type PostgreSQL | NULL autorisé | Explication |
| --- | --- | --- | --- |
| `generated_at` | `TIMESTAMPTZ` | Oui | Date de la dernière activation réussie, après confirmation d’un code TOTP. Malgré son nom, ce n’est pas la date de génération du mot de passe. Démarre les six mois de validité des identifiants. Vaut `NULL` avant l’activation et pendant un renouvellement en attente d’activation. |
| `expired` | `BOOLEAN` | Non | Indicateur d’expiration des identifiants. Initialisé à `false` par l’application, positionné à `true` lorsque certains contrôles constatent l’expiration, puis remis à `false` à l’activation réussie. La date doit aussi être vérifiée : `false` ne garantit pas que les identifiants sont encore valides. |
| `mfa_confirmed` | `BOOLEAN` | Non | Indique si le second facteur a été confirmé. Initialisé à `false`, passe à `true` après validation du premier code TOTP. Revient à `false` lors du renouvellement. Une connexion nécessite cette confirmation. |
| `totp_ciphertext` | `TEXT` | Oui | Secret TOTP chiffré avec Fernet. Créé lors de la configuration de l’application d’authentification, puis utilisé pour vérifier ses codes à six chiffres. Ce n’est ni un code TOTP ni une image QR. Effacé au renouvellement avant la configuration du nouveau secret. |
| `last_totp_step` | `BIGINT` | Oui | Numéro du dernier intervalle TOTP accepté. Chaque intervalle dure 30 secondes ; son numéro correspond au temps Unix divisé par 30, arrondi à l’entier inférieur. Empêche d’accepter à nouveau le même intervalle ou un intervalle antérieur. Mis à jour à la confirmation et à l’authentification ; remis à `NULL` au renouvellement. |

L’expiration des identifiants est calculée ainsi : `expired = true` **ou** date
courante supérieure ou égale à `generated_at + 6 mois calendaires`.
La propriété `expires_at` exposée par le modèle est calculée ; ce n’est pas une
colonne de la base. Si le jour n’existe pas dans le mois cible, le dernier jour
de ce mois est utilisé.

### Remise du mot de passe

La remise permet de révéler une seule fois le mot de passe généré, via un lien
ou un QR code. Elle dispose d’un jeton distinct de celui d’activation.

| Colonne | Type PostgreSQL | NULL autorisé | Explication |
| --- | --- | --- | --- |
| `delivery_ciphertext` | `TEXT` | Oui | Copie du mot de passe chiffrée avec Fernet, conservée uniquement pour sa remise. Effacée dès la remise réussie, ou par la purge après expiration du lien. Le hachage `password_hash` reste conservé. |
| `delivery_digest` | `VARCHAR(64)` | Oui | Empreinte SHA-256 du jeton de remise. Unique lorsqu’elle est renseignée. Sert à retrouver le compte associé au lien de remise. Effacée après utilisation. |
| `delivery_expires_at` | `TIMESTAMPTZ` | Oui | Date limite du jeton de remise : 15 minutes après sa création à l’inscription ou au renouvellement. Effacée avec l’empreinte après utilisation ou purge. |

### Jeton d’activation

Le préfixe `enrollment` désigne le parcours d’activation : consultation de son
état, configuration du TOTP et confirmation du premier code. Le jeton peut
servir aux différentes étapes ; il est consommé à la confirmation réussie.

| Colonne | Type PostgreSQL | NULL autorisé | Explication |
| --- | --- | --- | --- |
| `enrollment_digest` | `VARCHAR(64)` | Oui | Empreinte SHA-256 du jeton d’activation, unique lorsqu’elle est renseignée. Créée à l’inscription ou au renouvellement, puis effacée après confirmation du TOTP. |
| `enrollment_expires_at` | `TIMESTAMPTZ` | Oui | Date limite du jeton d’activation : 15 minutes à partir de sa création à l’inscription ou au renouvellement. La remise du mot de passe ne redémarre pas ce délai. Effacée à l’activation réussie ou lors de la purge. |

### Jeton de renouvellement

Ce jeton est délivré lorsque l’utilisateur présente un mot de passe et un code
TOTP valides, mais que ses identifiants ont expiré. Il autorise uniquement le
renouvellement, sans ouvrir de session normale.

| Colonne | Type PostgreSQL | NULL autorisé | Explication |
| --- | --- | --- | --- |
| `renewal_digest` | `VARCHAR(64)` | Oui | Empreinte SHA-256 du jeton de renouvellement, unique lorsqu’elle est renseignée. Effacée lorsque le renouvellement génère le nouveau mot de passe et les nouveaux jetons de remise et d’activation. |
| `renewal_expires_at` | `TIMESTAMPTZ` | Oui | Date limite du jeton de renouvellement : 5 minutes après l’authentification ayant constaté l’expiration. Effacée lors du renouvellement ou de la purge. |

### Jeton de session

Ce jeton permet d’accéder au compte après une connexion réussie. Il est
réutilisable pendant sa validité. Une seule session est conservée par compte.

| Colonne | Type PostgreSQL | NULL autorisé | Explication |
| --- | --- | --- | --- |
| `session_digest` | `VARCHAR(64)` | Oui | Empreinte SHA-256 du jeton de session, unique lorsqu’elle est renseignée. Remplacée à chaque nouvelle connexion, ce qui invalide la session précédente. Effacée à la déconnexion, au renouvellement ou lorsque le service révoque la session pour expiration des identifiants. |
| `session_expires_at` | `TIMESTAMPTZ` | Oui | Date limite de la session : la plus proche entre 30 minutes après la connexion et l’expiration des identifiants. Les consultations du compte ne prolongent pas ce délai. Effacée avec l’empreinte à la révocation ou à la purge. |

## Durées et nettoyage

| Élément | Durée | Début du délai |
| --- | --- | --- |
| Remise du mot de passe | 15 minutes | Inscription ou renouvellement |
| Activation | 15 minutes | Inscription ou renouvellement |
| Renouvellement | 5 minutes | Authentification avec des identifiants expirés |
| Session | 30 minutes maximum, limitée par l’expiration des identifiants | Connexion réussie |
| Identifiants (mot de passe et second facteur) | 6 mois calendaires | Confirmation réussie du TOTP |

Les jetons bruts ne sont pas enregistrés en base. L’application calcule leur
empreinte pour les vérifier. À la date limite exacte, le jeton est déjà refusé,
même si son empreinte figure encore dans la table.

La [commande de maintenance](architecture.md#maintenance-locale) remet à `NULL`
les empreintes et les dates limites des jetons expirés. Pour la remise, elle
efface aussi `delivery_ciphertext`. Elle ne supprime ni le compte, ni le hachage
du mot de passe, ni le secret TOTP, et ne met pas à jour `expired`.
Cette purge n’est pas planifiée automatiquement.

## Contraintes et valeurs initiales

`id` est la clé primaire. `username` et chacun des quatre champs `*_digest`
possèdent leur propre contrainte d’unicité. Plusieurs utilisateurs peuvent avoir
`NULL` dans une colonne de jeton. Il n’y a pas de clé étrangère dans `users`.

Les valeurs initiales sont fournies par l’application. En particulier, la
migration ne définit pas de valeur par défaut SQL pour les booléens, les dates
ou l’UUID : une insertion SQL manuelle doit renseigner les colonnes obligatoires.

## Table technique `alembic_version`

| Colonne | Type PostgreSQL | NULL autorisé | Explication |
| --- | --- | --- | --- |
| `version_num` | `VARCHAR(32)` | Non | Identifiant de la révision appliquée, géré par Alembic comme clé primaire. Pour le schéma actuel, la révision est `0001`. Permet de déterminer les prochaines migrations à exécuter. |

Cette table est gérée par l’outil de migration ; elle ne contient aucune donnée
utilisateur.

## Sources des règles métier

- [Inscription, remise et renouvellement](../functions/generate-password/service.py)
- [Configuration et confirmation du TOTP](../functions/generate-2fa/service.py)
- [Connexion et déconnexion](../functions/authenticate/service.py)
- [Durées des jetons](../src/cofrap/application/capabilities.py)
- [Calcul de l’expiration des identifiants](../src/cofrap/domain/models.py)
- [Hachage, chiffrement et contrôle TOTP](../src/cofrap/infrastructure/security.py)
- [Purge des jetons expirés](../src/cofrap/infrastructure/maintenance.py)
