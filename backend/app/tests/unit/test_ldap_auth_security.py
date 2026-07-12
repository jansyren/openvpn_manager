"""Security-focused unit tests for LDAP authentication.

Covers:
- SEC-2: the login username is RFC-4515 escaped before being interpolated
  into the LDAP search filter (filter-injection prevention), while the
  admin-configured user_filter / username_attr are left untouched.
- SEC-3: an empty or whitespace-only password is rejected before any user
  bind is attempted (anonymous-bind auth-bypass prevention).
"""
import pytest

from app.services import ldap_service


class _FakeConfig:
    """Minimal stand-in for LdapConfig for filter construction."""

    def __init__(self, user_filter: str, username_attr: str) -> None:
        self.user_filter = user_filter
        self.username_attr = username_attr


def test_build_user_filter_escapes_malicious_username():
    config = _FakeConfig(user_filter="(objectClass=person)", username_attr="uid")

    result = ldap_service._build_user_filter(config, "*)(uid=admin")

    # The injection metacharacters from the username must be escaped, so a raw
    # unescaped injection payload must NOT appear in the resulting filter.
    assert "*)(uid=admin" not in result
    # RFC 4515 escaping: '*' -> \2a, '(' -> \28, ')' -> \29
    assert "\\2a" in result  # escaped '*'
    assert "\\28" in result  # escaped '('
    assert "\\29" in result  # escaped ')'

    # The admin-configured pieces are preserved verbatim (NOT escaped).
    assert result.startswith("(&(objectClass=person)(uid=")
    assert "(objectClass=person)" in result


def test_build_user_filter_preserves_admin_config_unescaped():
    # A user_filter containing parentheses/asterisks (legitimate LDAP syntax)
    # must be preserved exactly, not escaped.
    config = _FakeConfig(
        user_filter="(&(objectClass=user)(!(userAccountControl=2)))",
        username_attr="sAMAccountName",
    )

    result = ldap_service._build_user_filter(config, "alice")

    assert result == (
        "(&(&(objectClass=user)(!(userAccountControl=2)))(sAMAccountName=alice))"
    )


def test_build_user_filter_normal_username_unchanged():
    config = _FakeConfig(user_filter="(objectClass=person)", username_attr="uid")

    result = ldap_service._build_user_filter(config, "jdoe")

    assert result == "(&(objectClass=person)(uid=jdoe))"


@pytest.mark.parametrize("bad_password", ["", "   ", "\t", "\n", "  \t\n "])
def test_authenticate_rejects_empty_or_whitespace_password(bad_password):
    """An empty/whitespace password must raise BEFORE any bind is attempted.

    We deliberately do NOT patch _bind_service_account: if the guard were
    missing, the code would fall through and try to contact a (nonexistent)
    LDAP server, which would raise a different error. Asserting on the
    specific ValueError message proves the guard fired first.
    """
    config = _FakeConfig(user_filter="(objectClass=person)", username_attr="uid")

    with pytest.raises(ValueError, match="Password verification failed"):
        ldap_service._do_authenticate(config, "alice", bad_password)
