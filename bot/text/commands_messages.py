from __future__ import annotations


def guild_only() -> str:
    return "This command can only be used in a server channel."


def dm_only() -> str:
    return "This command can only be used in DMs."


def no_permission() -> str:
    return "You don't have permission to use this command."


def unknown_mode() -> str:
    return "Unknown mode."


def invalid_m_ss() -> str:
    return "Invalid format. Use M:SS, e.g. 1:30."


def invalid_seconds() -> str:
    return "Invalid value. Use seconds as a positive number, e.g. 0.3."


def must_be_admin() -> str:
    return "You must be a server administrator to use this command."


def must_specify_command() -> str:
    return "You must specify which command to configure."

