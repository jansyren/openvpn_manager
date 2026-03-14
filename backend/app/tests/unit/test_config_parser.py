"""Unit tests for the OpenVPN config parser."""
import pytest

from app.services.config_parser import parse_config, serialize_config


def test_parse_simple_directives():
    content = """
proto udp
port 1194
dev tun
server 10.8.0.0 255.255.255.0
"""
    parsed = parse_config(content)
    assert parsed.directives["proto"] == "udp"
    assert parsed.directives["port"] == "1194"
    assert parsed.directives["dev"] == "tun"
    assert parsed.directives["server"] == "10.8.0.0 255.255.255.0"


def test_parse_flag_directives():
    content = """
persist-key
persist-tun
client-to-client
"""
    parsed = parse_config(content)
    assert parsed.directives["persist-key"] is True
    assert parsed.directives["persist-tun"] is True
    assert parsed.directives["client-to-client"] is True


def test_parse_multi_directives():
    content = """
push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 8.8.8.8"
push "dhcp-option DNS 8.8.4.4"
"""
    parsed = parse_config(content)
    assert len(parsed.directives["push"]) == 3
    assert '"redirect-gateway def1 bypass-dhcp"' in parsed.directives["push"]


def test_parse_inline_blocks():
    content = """
dev tun
<ca>
-----BEGIN CERTIFICATE-----
MIID...
-----END CERTIFICATE-----
</ca>
<cert>
-----BEGIN CERTIFICATE-----
MIID...
-----END CERTIFICATE-----
</cert>
"""
    parsed = parse_config(content)
    assert "ca" in parsed.inline_blocks
    assert "cert" in parsed.inline_blocks
    assert "BEGIN CERTIFICATE" in parsed.inline_blocks["ca"]


def test_parse_comments_ignored():
    content = """
# This is a comment
; This is also a comment
proto tcp
"""
    parsed = parse_config(content)
    assert "proto" in parsed.directives
    assert "# This is a comment" not in parsed.directives
    assert parsed.directives["proto"] == "tcp"


def test_parse_empty_content():
    parsed = parse_config("")
    assert parsed.directives == {}
    assert parsed.inline_blocks == {}


def test_round_trip():
    """Parse then serialize should produce equivalent directives."""
    content = """proto udp
port 1194
dev tun
persist-key
push "redirect-gateway def1"
push "dhcp-option DNS 8.8.8.8"
"""
    parsed = parse_config(content)
    serialized = serialize_config(parsed)
    reparsed = parse_config(serialized)

    assert reparsed.directives["proto"] == "udp"
    assert reparsed.directives["port"] == "1194"
    assert reparsed.directives["persist-key"] is True
    assert len(reparsed.directives["push"]) == 2


def test_serialize_config():
    from app.services.config_parser import ParsedConfig

    config = ParsedConfig(
        directives={
            "proto": "udp",
            "port": "1194",
            "persist-key": True,
            "push": ['"redirect-gateway def1"', '"dhcp-option DNS 8.8.8.8"'],
        }
    )
    output = serialize_config(config)
    assert "proto udp" in output
    assert "persist-key" in output
    assert 'push "redirect-gateway def1"' in output
    assert 'push "dhcp-option DNS 8.8.8.8"' in output
