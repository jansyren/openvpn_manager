"""Unit tests for the LDAP-sync two-pass group accumulation (REF-1)."""
from app.services.ldap_sync_service import accumulate_members


def test_accumulate_unions_group_dns_for_multi_group_member():
    alice_g1 = {"username": "alice", "dn": "cn=alice", "email": "a@x", "display_name": "Alice"}
    alice_g2 = {"username": "alice", "dn": "cn=alice", "email": "a@x", "display_name": "Alice"}
    bob = {"username": "bob", "dn": "cn=bob", "email": None, "display_name": "Bob"}

    result = accumulate_members(
        [
            ("cn=admins,dc=x", [alice_g1]),
            ("cn=vpn-users,dc=x", [alice_g2, bob]),
        ]
    )

    assert set(result.keys()) == {"alice", "bob"}
    # alice was found in both groups → both DNs accumulated
    assert result["alice"]["group_dns"] == {"cn=admins,dc=x", "cn=vpn-users,dc=x"}
    assert result["bob"]["group_dns"] == {"cn=vpn-users,dc=x"}
    # member fields are preserved
    assert result["alice"]["email"] == "a@x"


def test_accumulate_empty_input():
    assert accumulate_members([]) == {}


def test_accumulate_single_group():
    result = accumulate_members([("cn=g,dc=x", [{"username": "u", "dn": "cn=u"}])])
    assert result["u"]["group_dns"] == {"cn=g,dc=x"}
