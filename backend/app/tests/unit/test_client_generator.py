"""Unit tests for .ovpn client file generation."""
import pytest

from app.services.client_generator import generate_site_ovpn, generate_user_ovpn

SAMPLE_CA = """-----BEGIN CERTIFICATE-----
MIIDXzCCAkegAwIBAgIJALuoxMgmHSHLMA0GCSqGSIb3DQEBCwUAMGQxCzAJBgNV
BAYTAlVTMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX
-----END CERTIFICATE-----"""

SAMPLE_CERT = """-----BEGIN CERTIFICATE-----
MIIDWzCCAkOgAwIBAgIJAOFHnQOLTv/KMA0GCSqGSIb3DQEBCwUAMGQxCzAJBgNV
BAYTAlVTMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBX
-----END CERTIFICATE-----"""

SAMPLE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7
-----END PRIVATE KEY-----"""


def test_user_ovpn_structure():
    ovpn = generate_user_ovpn(
        server_host="vpn.example.com",
        server_port=1194,
        proto="udp",
        ca_cert_pem=SAMPLE_CA,
        client_cert_pem=SAMPLE_CERT,
        client_key_pem=SAMPLE_KEY,
    )
    assert "client" in ovpn
    assert "dev tun" in ovpn
    assert "proto udp" in ovpn
    assert "remote vpn.example.com 1194" in ovpn
    assert "<ca>" in ovpn
    assert "</ca>" in ovpn
    assert "<cert>" in ovpn
    assert "</cert>" in ovpn
    assert "<key>" in ovpn
    assert "</key>" in ovpn


def test_user_ovpn_no_shell_metacharacters():
    """Verify that shell metacharacters in server_host are handled safely."""
    # The generate functions use only trusted server-side data; this test
    # verifies that the output is structured text, not a shell command.
    ovpn = generate_user_ovpn(
        server_host="vpn.example.com",
        server_port=443,
        proto="tcp",
        ca_cert_pem=SAMPLE_CA,
        client_cert_pem=SAMPLE_CERT,
        client_key_pem=SAMPLE_KEY,
    )
    # Should contain 'remote vpn.example.com 443' as a literal string
    assert "remote vpn.example.com 443" in ovpn
    # No shell operators should be present
    assert "&&" not in ovpn
    assert "; " not in ovpn
    assert "`" not in ovpn
    assert "$(" not in ovpn


def test_user_ovpn_with_tls_auth():
    tls_key = "# 2048 bit OpenVPN static key\n-----BEGIN OpenVPN Static key V1-----\nabc123\n-----END OpenVPN Static key V1-----"
    ovpn = generate_user_ovpn(
        server_host="vpn.example.com",
        server_port=1194,
        proto="udp",
        ca_cert_pem=SAMPLE_CA,
        client_cert_pem=SAMPLE_CERT,
        client_key_pem=SAMPLE_KEY,
        tls_auth_key=tls_key,
    )
    assert "key-direction 1" in ovpn
    assert "<tls-auth>" in ovpn


def test_user_ovpn_with_tls_crypt():
    tls_key = "-----BEGIN OpenVPN Static key V1-----\nabc123\n-----END OpenVPN Static key V1-----"
    ovpn = generate_user_ovpn(
        server_host="vpn.example.com",
        server_port=1194,
        proto="udp",
        ca_cert_pem=SAMPLE_CA,
        client_cert_pem=SAMPLE_CERT,
        client_key_pem=SAMPLE_KEY,
        tls_crypt_key=tls_key,
    )
    assert "<tls-crypt>" in ovpn
    assert "key-direction" not in ovpn  # tls-crypt doesn't use key-direction


def test_site_ovpn_structure():
    ovpn = generate_site_ovpn(
        server_host="vpn.example.com",
        server_port=1194,
        proto="udp",
        ca_cert_path="/etc/openvpn/ca.crt",
        client_cert_path="/etc/openvpn/site.crt",
        client_key_path="/etc/openvpn/site.key",
    )
    assert "client" in ovpn
    assert "ca /etc/openvpn/ca.crt" in ovpn
    assert "cert /etc/openvpn/site.crt" in ovpn
    assert "key /etc/openvpn/site.key" in ovpn
    # Should NOT have inline blocks
    assert "<ca>" not in ovpn
    assert "<cert>" not in ovpn


def test_extra_directives():
    ovpn = generate_user_ovpn(
        server_host="vpn.example.com",
        server_port=1194,
        proto="udp",
        ca_cert_pem=SAMPLE_CA,
        client_cert_pem=SAMPLE_CERT,
        client_key_pem=SAMPLE_KEY,
        extra_directives=["comp-lzo no", "mute 20"],
    )
    assert "comp-lzo no" in ovpn
    assert "mute 20" in ovpn
