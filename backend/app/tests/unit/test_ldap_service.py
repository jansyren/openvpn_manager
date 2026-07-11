"""Unit tests for LDAP role-resolution helpers."""
from app.services import ldap_service


class _FakeMapping:
    def __init__(self, group_dn: str, role: str) -> None:
        self.group_dn = group_dn
        self.role = role


def test_determine_all_roles_returns_every_matching_role():
    mappings = [
        _FakeMapping("cn=admins,dc=example,dc=com", "admin"),
        _FakeMapping("cn=vpn-users,dc=example,dc=com", "vpn_user"),
        _FakeMapping("cn=operators,dc=example,dc=com", "operator"),
    ]
    # User is in both the admins group and the vpn-users group.
    group_dns = ["cn=admins,dc=example,dc=com", "cn=vpn-users,dc=example,dc=com"]

    roles = ldap_service.determine_all_roles(group_dns, mappings)

    assert roles == {"admin", "vpn_user"}


def test_determine_role_still_picks_highest_priority():
    mappings = [
        _FakeMapping("cn=admins,dc=example,dc=com", "admin"),
        _FakeMapping("cn=vpn-users,dc=example,dc=com", "vpn_user"),
    ]
    group_dns = ["cn=admins,dc=example,dc=com", "cn=vpn-users,dc=example,dc=com"]

    assert ldap_service.determine_role(group_dns, mappings) == "admin"


def test_pick_primary_role_from_arbitrary_set():
    assert ldap_service.pick_primary_role({"admin", "vpn_user"}) == "admin"
    assert ldap_service.pick_primary_role({"viewer", "vpn_user"}) == "viewer"
    assert ldap_service.pick_primary_role(set()) is None


def test_determine_all_roles_case_insensitive_dn_matching():
    mappings = [_FakeMapping("CN=Admins,DC=Example,DC=Com", "admin")]
    group_dns = ["cn=admins,dc=example,dc=com"]

    assert ldap_service.determine_all_roles(group_dns, mappings) == {"admin"}


def test_determine_all_roles_no_match_returns_empty_set():
    mappings = [_FakeMapping("cn=admins,dc=example,dc=com", "admin")]
    group_dns = ["cn=someone-else,dc=example,dc=com"]

    assert ldap_service.determine_all_roles(group_dns, mappings) == set()
