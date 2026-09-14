from cofrap.domain.errors import (
    BackendUnavailable,
    CredentialsExpired,
    EnrollmentRequired,
    InvalidCredentials,
    InvalidInput,
    InvalidToken,
    UsernameTaken,
)

STATUSES = {
    UsernameTaken: 409,
    InvalidCredentials: 401,
    InvalidToken: 401,
    EnrollmentRequired: 409,
    CredentialsExpired: 403,
    BackendUnavailable: 503,
    InvalidInput: 422,
}
ERROR_TYPES = {kind.code: kind for kind in STATUSES}
