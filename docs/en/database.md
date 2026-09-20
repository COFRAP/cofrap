# Database — column reference

The PostgreSQL database has one business table, `users`. Each row holds one user,
their credentials, and their temporary tokens. Tokens are stored in that same
row. There is no separate session table. Alembic also uses an internal table,
`alembic_version`, to track applied migrations.

This guide describes the [initial schema](../../migrations/versions/0001_create_users.py)
and the [SQLAlchemy model](../../src/cofrap/infrastructure/database.py).

## How to read the values

- **Allows NULL**: the column can have no value. This usually means a step is
  incomplete, a token is missing, or data has been removed.
- **Digest / hash**: a result used to check a value without keeping the original.
  Passwords use Argon2id. Tokens use SHA-256, stored as 64 hexadecimal characters.
- **Encryption**: protection that can be reversed with the application key.
  Fernet lets the app retrieve the password before delivery and the TOTP secret
  to check codes.
- Dates use the PostgreSQL type `TIMESTAMP WITH TIME ZONE` (`TIMESTAMPTZ`).
  The application calculates times in UTC.

## The `users` table: 18 columns

### Identity and password

| Column | PostgreSQL type | Allows NULL | Meaning |
| --- | --- | --- | --- |
| `id` | `UUID` | No | Unique internal user ID. The application generates a UUID v4 at registration. This is the primary key and stays the same on renewal. |
| `username` | `VARCHAR(64)` | No | The user's login name. A unique constraint prevents two accounts from having the same stored name. |
| `password_hash` | `TEXT` | No | Argon2id hash of the generated password. Used to check the password at login without decrypting it. Replaced on renewal. |
| `created_at` | `TIMESTAMPTZ` | No | Account creation time. It stays the same during activation and renewal. |

### Activation, validity, and second factor

| Column | PostgreSQL type | Allows NULL | Meaning |
| --- | --- | --- | --- |
| `generated_at` | `TIMESTAMPTZ` | Yes | Time of the last successful activation, after a TOTP code is confirmed. Despite its name, this is not the password generation time. It starts the six-month credential lifetime. It is `NULL` before activation and during renewal while activation is pending. |
| `expired` | `BOOLEAN` | No | Credential expiry flag. The app starts it at `false`, sets it to `true` when certain checks detect expiry, and resets it to `false` after successful activation. The date must also be checked: `false` does not guarantee that credentials are still valid. |
| `mfa_confirmed` | `BOOLEAN` | No | Whether the second factor has been confirmed. Starts at `false` and becomes `true` after the first valid TOTP code. Returns to `false` on renewal. Login requires this confirmation. |
| `totp_ciphertext` | `TEXT` | Yes | TOTP secret encrypted with Fernet. Created when the authenticator app is set up, then used to check its six-digit codes. It is neither a TOTP code nor a QR image. Removed on renewal before the new secret is set up. |
| `last_totp_step` | `BIGINT` | Yes | Number of the last accepted TOTP interval. Each interval lasts 30 seconds. Its number is Unix time divided by 30, rounded down. Prevents the same or an earlier interval from being accepted again. Updated at confirmation and login; reset to `NULL` on renewal. |

Credentials are expired when `expired = true` **or** the current time is at or
after `generated_at + 6 calendar months`. The model's `expires_at` property is
calculated, not stored in a database column. If the day does not exist in the
target month, the last day of that month is used.

### Password delivery

Delivery reveals the generated password once, through a link or QR code.
It has its own token, separate from the enrollment token.

| Column | PostgreSQL type | Allows NULL | Meaning |
| --- | --- | --- | --- |
| `delivery_ciphertext` | `TEXT` | Yes | Password copy encrypted with Fernet, kept only for delivery. Removed after successful delivery, or by cleanup after the link expires. The `password_hash` remains stored. |
| `delivery_digest` | `VARCHAR(64)` | Yes | SHA-256 hash of the delivery token. Unique when set. Used to find the account linked to the delivery URL. Removed after use. |
| `delivery_expires_at` | `TIMESTAMPTZ` | Yes | Delivery token deadline: 15 minutes after creation at registration or renewal. Removed with the hash after use or cleanup. |

### Enrollment token

The `enrollment` prefix refers to account activation: checking its status,
setting up TOTP, and confirming the first code. The token can be used across
these steps. It is used up after successful confirmation.

| Column | PostgreSQL type | Allows NULL | Meaning |
| --- | --- | --- | --- |
| `enrollment_digest` | `VARCHAR(64)` | Yes | SHA-256 hash of the enrollment token, unique when set. Created at registration or renewal, then removed after TOTP confirmation. |
| `enrollment_expires_at` | `TIMESTAMPTZ` | Yes | Enrollment token deadline: 15 minutes from creation at registration or renewal. Password delivery does not restart this timer. Removed after successful activation or during cleanup. |

### Renewal token

This token is issued when the user provides a valid password and TOTP code but
their credentials have expired. It only allows renewal and does not open a normal session.

| Column | PostgreSQL type | Allows NULL | Meaning |
| --- | --- | --- | --- |
| `renewal_digest` | `VARCHAR(64)` | Yes | SHA-256 hash of the renewal token, unique when set. Removed when renewal generates a new password and new delivery and enrollment tokens. |
| `renewal_expires_at` | `TIMESTAMPTZ` | Yes | Renewal token deadline: 5 minutes after the login that detected expiry. Removed during renewal or cleanup. |

### Session token

This token allows access to the account after a successful login. It can be
reused until it expires. Each account has only one stored session.

| Column | PostgreSQL type | Allows NULL | Meaning |
| --- | --- | --- | --- |
| `session_digest` | `VARCHAR(64)` | Yes | SHA-256 hash of the session token, unique when set. Replaced at each new login, which invalidates the previous session. Removed on logout, renewal, or when the service revokes the session because credentials have expired. |
| `session_expires_at` | `TIMESTAMPTZ` | Yes | Session deadline: the earlier of 30 minutes after login or credential expiry. Reading the account does not extend it. Removed with the hash on revocation or cleanup. |

## Lifetimes and cleanup

| Item | Lifetime | Starts at |
| --- | --- | --- |
| Password delivery | 15 minutes | Registration or renewal |
| Enrollment | 15 minutes | Registration or renewal |
| Renewal | 5 minutes | Login with expired credentials |
| Session | Up to 30 minutes, ending no later than credential expiry | Successful login |
| Credentials (password and second factor) | 6 calendar months | Successful TOTP confirmation |

Raw tokens are not stored in the database. The app calculates their hashes to
check them. At the exact deadline, a token is already rejected, even if its hash
is still in the table.

The [maintenance command](architecture.md#local-maintenance) sets expired token
hashes and deadlines to `NULL`. For delivery, it also removes
`delivery_ciphertext`. It does not delete the account, password hash, or TOTP
secret, and it does not update `expired`. This cleanup is not scheduled automatically.

## Constraints and initial values

`id` is the primary key. `username` and each of the four `*_digest` fields have
their own unique constraint. Several users can have `NULL` in a token column.
There are no foreign keys in `users`.

The application supplies initial values. In particular, the migration does not
set SQL defaults for booleans, dates, or the UUID. A manual SQL insert must
provide all required columns.

## Internal table: `alembic_version`

| Column | PostgreSQL type | Allows NULL | Meaning |
| --- | --- | --- | --- |
| `version_num` | `VARCHAR(32)` | No | Applied revision ID, managed by Alembic as the primary key. The current schema revision is `0001`. Used to find the next migrations to run. |

The migration tool manages this table. It holds no user data.

## Business rule source files

- [Registration, delivery, and renewal](../../functions/generate-password/service.py)
- [TOTP setup and confirmation](../../functions/generate-2fa/service.py)
- [Login and logout](../../functions/authenticate/service.py)
- [Token lifetimes](../../src/cofrap/application/capabilities.py)
- [Credential expiry calculation](../../src/cofrap/domain/models.py)
- [Hashing, encryption, and TOTP checks](../../src/cofrap/infrastructure/security.py)
- [Expired token cleanup](../../src/cofrap/infrastructure/maintenance.py)
