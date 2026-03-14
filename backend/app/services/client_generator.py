"""
Generates .ovpn client configuration files.

User clients: all certificates embedded inline using <ca>, <cert>, <key> blocks.
Site clients: references to external certificate files (no embedding).

SECURITY: String formatting uses only trusted server-side data.
No user-supplied content is embedded without sanitisation.
"""


def generate_user_ovpn(
    server_host: str,
    server_port: int,
    proto: str,
    ca_cert_pem: str,
    client_cert_pem: str,
    client_key_pem: str,
    tls_auth_key: str | None = None,
    tls_crypt_key: str | None = None,
    auth_user_pass: bool = False,
    server_poll_timeout: int = 4,
    data_ciphers: str = "AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305",
    data_ciphers_fallback: str = "AES-256-CBC",
    auth: str = "SHA256",
    extra_directives: list[str] | None = None,
) -> str:
    """Generate a .ovpn file with all certificates embedded inline."""

    lines = [
        "client",
        f"server-poll-timeout {server_poll_timeout}",
        "dev tun",
        "dev-type tun",
        "ns-cert-type server",
        f"proto {proto}",
        f"remote {server_host} {server_port}",
        "",
        "resolv-retry infinite",
        "nobind",
        "persist-key",
        "persist-tun",
        "",
        "# Security",
        f"data-ciphers {data_ciphers}",
        f"data-ciphers-fallback {data_ciphers_fallback}",
    ]

    if auth_user_pass:
        lines.append("auth-user-pass")

    lines.append(f"auth {auth}")

    if extra_directives:
        lines.append("")
        lines.extend(extra_directives)

    lines.append("")
    lines.append("# Certificates and keys")

    # Inline CA
    lines.append("<ca>")
    lines.append(ca_cert_pem.strip())
    lines.append("</ca>")
    lines.append("")

    # Inline client cert
    lines.append("<cert>")
    lines.append(_extract_cert_body(client_cert_pem))
    lines.append("</cert>")
    lines.append("")

    # Inline client key
    lines.append("<key>")
    lines.append(client_key_pem.strip())
    lines.append("</key>")
    lines.append("")

    # TLS auth / crypt
    if tls_crypt_key:
        lines.append("<tls-crypt>")
        lines.append(tls_crypt_key.strip())
        lines.append("</tls-crypt>")
        lines.append("")
    elif tls_auth_key:
        lines.append("key-direction 1")
        lines.append("<tls-auth>")
        lines.append(tls_auth_key.strip())
        lines.append("</tls-auth>")
        lines.append("")

    lines.append("verb 3")
    lines.append("")

    return "\n".join(lines)


def generate_site_ovpn(
    server_host: str,
    server_port: int,
    proto: str,
    ca_cert_path: str,
    client_cert_path: str,
    client_key_path: str,
    tls_auth_path: str | None = None,
    data_ciphers: str = "AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305",
    data_ciphers_fallback: str = "AES-256-CBC",
    auth: str = "SHA256",
    extra_directives: list[str] | None = None,
) -> str:
    """Generate a .ovpn file with external certificate file references."""

    lines = [
        "client",
        "dev tun",
        f"proto {proto}",
        f"remote {server_host} {server_port}",
        "resolv-retry infinite",
        "nobind",
        "persist-key",
        "persist-tun",
        "remote-cert-tls server",
        f"data-ciphers {data_ciphers}",
        f"data-ciphers-fallback {data_ciphers_fallback}",
        f"auth {auth}",
        f"ca {ca_cert_path}",
        f"cert {client_cert_path}",
        f"key {client_key_path}",
        "verb 3",
    ]

    if tls_auth_path:
        lines.append(f"tls-auth {tls_auth_path} 1")

    if extra_directives:
        lines.extend(extra_directives)

    return "\n".join(lines) + "\n"


def _extract_cert_body(pem: str) -> str:
    """Extract only the certificate portion (strip any chain or extra certs)."""
    lines = pem.strip().splitlines()
    in_cert = False
    cert_lines: list[str] = []

    for line in lines:
        if line.startswith("-----BEGIN CERTIFICATE-----"):
            in_cert = True
            cert_lines.append(line)
        elif line.startswith("-----END CERTIFICATE-----"):
            cert_lines.append(line)
            break  # take only the first cert
        elif in_cert:
            cert_lines.append(line)

    return "\n".join(cert_lines)
