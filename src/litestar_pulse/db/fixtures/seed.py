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
    ("_EnumKeyMgr_", [ENUMKEY_CREATE, ENUMKEY_MODIFY, ENUMKEY_DELETE, ENUMKEY_VIEW]),
    (
        "_UserDomainMgr_",
        [USERDOMAIN_CREATE, USERDOMAIN_MODIFY, USERDOMAIN_DELETE, USERDOMAIN_VIEW],
    ),
    ("_UserMgr_", [USER_CREATE, USER_MODIFY, USER_DELETE, USER_VIEW]),
    (
        "_GroupMgr_",
        [
            GROUP_CREATE,
            GROUP_MODIFY,
            GROUP_DELETE,
            GROUP_ADDUSER,
            GROUP_DELUSER,
            GROUP_VIEW,
        ],
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
            (ENUMKEY_CREATE, "create new EnumKey (EK)"),
            (ENUMKEY_MODIFY, "modify EnumKey(EK)"),
            (ENUMKEY_VIEW, "view EnumKey(EK)"),
            (ENUMKEY_DELETE, "delete EnumKey (EK)"),
            (USERDOMAIN_CREATE, "create new userdomain"),
            (USERDOMAIN_MODIFY, "modify userdomain data"),
            (USERDOMAIN_VIEW, "view userdomain data"),
            (USERDOMAIN_DELETE, "delete userdomain data"),
            (USER_CREATE, "create new user"),
            (USER_MODIFY, "modify user data"),
            (USER_VIEW, "view user data"),
            (USER_DELETE, "delete user data"),
            (GROUP_CREATE, "create new group"),
            (GROUP_MODIFY, "modify group data"),
            (GROUP_VIEW, "view group data"),
            (GROUP_DELETE, "delete group data"),
            (GROUP_ADDUSER, "add new user to group"),
            (GROUP_DELUSER, "remove user from group"),
        ],
    ),
    (
        "@ACTIONLOG",
        "ActionLog",
        [
            ("~user/add", ":: added new user %s"),
            ("~user/mod", ":: modified user %s"),
            ("~user/del", ":: deleted user %s"),
            ("~group/add", ":: added new group %s"),
            ("~group/mod", ":: modified group %s"),
            ("~group/del", ":: deleted group %s"),
            ("~group/adduser", ":: added to group %s user %s"),
            ("~group/deluser", ":: deleted from group %s user %s"),
            ("~ek/add", ":: added new EnumKey %s"),
            ("~ek/mod", ":: modified EnumKey %s"),
            ("~ek/del", ":: deleted EnumKey %s"),
            ("~userclass/add", ":: added new userclass %s"),
            ("~userclass/mod", ":: modified userclass %s"),
            ("~userclass/del", ":: deleted userclass %s"),
        ],
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
