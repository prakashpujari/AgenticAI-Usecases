ROLE_PERMISSIONS = {
    "PRODUCT_OWNER": ["create", "read"],
    "DEVELOPER": ["read"],
}

# Fallback email-to-role map (used when role is not supplied explicitly)
USER_ROLES = {
    "alice@company.com": "PRODUCT_OWNER",
}


def check_permission(user: str, action: str, role: str | None = None) -> None:
    """
    Verify that the user/role has permission to perform `action`.

    Priority:
      1. Use the `role` argument if provided (sent by the agent from the request).
      2. Fall back to the USER_ROLES lookup (legacy / admin overrides).
    """
    effective_role = role or USER_ROLES.get(user)
    if action not in ROLE_PERMISSIONS.get(effective_role, []):
        raise PermissionError(
            f"Access denied: role '{effective_role}' cannot perform '{action}'."
        )
