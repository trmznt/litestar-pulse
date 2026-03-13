from litestar_pulse.lib.roles import *

USERDOMAINS = [
    (
        "_SYSTEM_",  # userdomain name
        "Litestar-Pulse System",  # userdomain description
        "",  # userdomain URI referer
        {},  # userdomain credscheme
        "Internal",  # userdomain type
        [
            # (login, email, lastname, firstname, institution, primary_group, password, [(group, role), ...])
            (
                "sysadm",
                "sysadm@localhost",
                "",
                "",
                "",
                "_SysAdm_",
                "?",
                [("_SysAdm_", "A"), ("_User_", "A")],
            ),
            (
                "dbadm",
                "dbadm@localhost",
                "",
                "",
                "",
                "_DataAdm_",
                "{X}",
                [("_DataAdm_", "A")],
            ),
            (
                "anonymous",
                "anonymous@localhost",
                "",
                "",
                "",
                "_User_",
                "?",
                [("_User_", "M")],
            ),
        ],
    ),
]


GROUPS = [
    # (group_name, [assigned_enumkeys for roles])
    ("__default__", [PUBLIC]),
    ("_SysAdm_", [SYSADM, SYSVIEW]),
    ("_EnumKeyMgr_", [ENUMKEY_MANAGE]),
    (
        "_UserDomainMgr_",
        [USERDOMAIN_MANAGE],
    ),
    ("_UserMgr_", [USER_MANAGE]),
    (
        "_GroupMgr_",
        [GROUP_MANAGE, USERGROUP_MANAGE],
    ),
    ("_DataAdm_", [DATAADM, DATAVIEW]),
    ("_LogViewer_", []),
    ("_SysViewer_", [SYSVIEW]),
    ("_User_", [USER]),
]

ENUMKEYS = [
    (
        "@BASIC",  # enumkey name
        "Basic common keywords",  # enumkey description
        [
            # (enumkey name, enumkey description) for child enumkeys
            ("", ""),
            ("X", "undefined"),
        ],
    ),
    (
        "@USERDOMAIN_TYPE",
        "UserDomain types",
        [
            ("Internal", "internal userdomain managed by Litestar Pulse"),
            ("LDAP", "LDAP userdomain managed by external LDAP server"),
        ],
    ),
    (
        "@ROLES",
        "Group roles",
        [
            (SYSADM, "system administrator role"),
            (SYSVIEW, "system viewer role"),
            (DATAADM, "data administrator role"),
            (DATAVIEW, "data viewer role"),
            (PUBLIC, "public role - all visitor"),
            (USER, "authenticated user role"),
            (GUEST, "guest / anonymous user role"),
            (ENUMKEY_MANAGE, "manage EnumKey (EK)"),
            (ENUMKEY_MODIFY, "modify EK data"),
            (ENUMKEY_VIEW, "view EK data"),
            (USERDOMAIN_MANAGE, "manage userdomain"),
            (USERDOMAIN_MODIFY, "modify userdomain data"),
            (USERDOMAIN_VIEW, "view userdomain data"),
            (USER_MANAGE, "manage user"),
            (USER_MODIFY, "modify user data"),
            (USER_VIEW, "view user data"),
            (GROUP_MANAGE, "manage group"),
            (GROUP_MODIFY, "modify group data"),
            (GROUP_VIEW, "view group data"),
            (USERGROUP_MANAGE, "manage user-group relationships"),
            (USERGROUP_MODIFY, "modify user-group relationships"),
            (USERGROUP_VIEW, "view user-group relationships"),
        ],
    ),
    (
        "@ACTIONLOG",
        "ActionLog",
        [],
    ),
    (
        "@FILETYPE",
        "File type",
        [
            ("file/file", ""),
            ("file/folder", ""),
            ("file/link", ""),
            ("file/content", ""),
        ],
    ),
    (
        "@MIMETYPE",
        "Mime type",
        [
            ("application/x-directory", ""),
            ("application/x-url", ""),
            ("image/png", ""),
            ("image/jpeg", ""),
            ("image/gif", ""),
            ("image/svg+xml"),
            ("application/pdf", ""),
            ("application/postscript", ""),
            ("application/xml", ""),
            ("application/json", ""),
            ("application/octet-stream", ""),
            ("application/unknown", ""),
            ("text/plain", ""),
            ("text/html", ""),
            ("text/xml", ""),
            ("text/x-rst", "mimetype reStructuredText"),  # reStructuredText
            ("text/x-markdown", "mimeype MarkDown"),  # markdown
            ("text/x-mako", "mimetype Mako template"),
        ],
    ),
]
