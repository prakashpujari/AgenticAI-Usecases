ROLE_PERMISSIONS = {
 "PRODUCT_OWNER": ["create","read"],
 "DEVELOPER": ["read"]
}

USER_ROLES = {
 "alice@company.com": "PRODUCT_OWNER"
}

def check_permission(user, action):
    role = USER_ROLES.get(user)
    if action not in ROLE_PERMISSIONS.get(role, []):
        raise PermissionError("Access Denied")
