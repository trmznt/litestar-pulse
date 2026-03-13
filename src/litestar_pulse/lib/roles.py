# Roles are mainly categorized to
# - VIEW can view the model
# - MODIFY can view and modify the model
# - MANAGE can view, modify, create, and delete the model


SYSADM = "~r|system-adm"
SYSVIEW = "~r|system-viewer"
DATAADM = "~r|data-adm"
DATAVIEW = "~r|data-viewer"
PUBLIC = "~r|public"
USER = "~r|user"
GUEST = "~r|guest"

ENUMKEY_MANAGE = "~r|enumkey|manage"
ENUMKEY_MODIFY = "~r|enumkey|modify"
ENUMKEY_VIEW = "~r|enumkey|view"

USERDOMAIN_MANAGE = "~r|userdomain|manage"
USERDOMAIN_MODIFY = "~r|userdomain|modify"
USERDOMAIN_VIEW = "~r|userdomain|view"

USER_MANAGE = "~r|user|manage"
USER_MODIFY = "~r|user|modify"
USER_VIEW = "~r|user|view"

GROUP_MANAGE = "~r|group|manage"
GROUP_MODIFY = "~r|group|modify"
GROUP_VIEW = "~r|group|view"

USERGROUP_MANAGE = "~r|usergroup|manage"
USERGROUP_MODIFY = "~r|usergroup|modify"
USERGROUP_VIEW = "~r|usergroup|view"


def is_sysadm(user):

    return user.has_roles(SYSADM)


# EOF
