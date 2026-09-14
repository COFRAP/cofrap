class DomainError(Exception):
    code = "invalid_operation"
    message = "Cette opération n’est pas disponible."

    def __init__(self):
        super().__init__(self.message)


class UsernameTaken(DomainError):
    code = "username_taken"
    message = "Ce nom d’utilisateur est déjà utilisé."


class InvalidCredentials(DomainError):
    code = "invalid_credentials"
    message = "Identifiants invalides ou code TOTP déjà utilisé."


class InvalidToken(DomainError):
    code = "invalid_token"
    message = "Ce lien ou cette autorisation a expiré ou a déjà été utilisé."


class EnrollmentRequired(DomainError):
    code = "enrollment_required"
    message = "Récupérez le mot de passe puis confirmez la double authentification."


class CredentialsExpired(DomainError):
    code = "credentials_expired"
    message = "Vos identifiants ont expiré. Reconnectez-vous pour les renouveler."


class BackendUnavailable(DomainError):
    code = "backend_unavailable"
    message = "Le service est temporairement indisponible. Réessayez dans un instant."


class InvalidInput(DomainError):
    code = "validation_error"
    message = "Vérifiez les champs saisis."
