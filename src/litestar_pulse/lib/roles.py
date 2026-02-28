SYSADM = "~r|system-adm"
SYSVIEW = "~r|system-viewer"
DATAADM = "~r|data-adm"
DATAVIEW = "~r|data-viewer"
PUBLIC = "~r|public"
USER = "~r|user"
GUEST = "~r|guest"

ENUMKEY_CREATE = "~r|enumkey|create"
ENUMKEY_MODIFY = "~r|enumkey|modify"
ENUMKEY_VIEW = "~r|enumkey|view"
ENUMKEY_DELETE = "~r|enumkey|delete"

USERDOMAIN_CREATE = "~r|userdomain|create"
USERDOMAIN_MODIFY = "~r|userdomain|modify"
USERDOMAIN_VIEW = "~r|userdomain|view"
USERDOMAIN_DELETE = "~r|userdomain|delete"

USER_CREATE = "~r|user|create"
USER_MODIFY = "~r|user|modify"
USER_VIEW = "~r|user|view"
USER_DELETE = "~r|user|delete"

GROUP_CREATE = "~r|group|create"
GROUP_MODIFY = "~r|group|modify"
GROUP_VIEW = "~r|group|view"
GROUP_DELETE = "~r|group|delete"
GROUP_ADDUSER = "~r|group|add-user"
GROUP_DELUSER = "~r|group|del-user"


def is_sysadm(user):

    return user.has_roles(SYSADM)


# EOF
