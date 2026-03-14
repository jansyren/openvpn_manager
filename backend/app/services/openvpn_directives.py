"""
Single authoritative source of truth for all OpenVPN server directives.

Each entry describes:
- name: directive name as it appears in the .conf file
- description: human-readable description shown in the UI
- directive_type: 'flag' (no value), 'single' (one value), 'multi' (repeatable)
- default: default value or None
- allowed_values: explicit allowed values or None (free-form)
- example: example value shown in the UI
- deprecated: whether this directive is deprecated
"""
from typing import Any

from pydantic import BaseModel


class DirectiveSpec(BaseModel):
    name: str
    description: str
    directive_type: str  # 'flag' | 'single' | 'multi'
    default: Any = None
    allowed_values: list[str] | None = None
    example: str | None = None
    deprecated: bool = False
    category: str = "general"


DIRECTIVES: dict[str, DirectiveSpec] = {
    # ── Network ──────────────────────────────────────────────────────────────
    "proto": DirectiveSpec(
        name="proto",
        description="Network protocol used for the VPN tunnel. 'udp' is recommended for performance; 'tcp' may be needed to traverse firewalls that block UDP.",
        directive_type="single",
        default="udp",
        allowed_values=["udp", "tcp", "udp6", "tcp6"],
        example="udp",
        category="network",
    ),
    "port": DirectiveSpec(
        name="port",
        description="TCP/UDP port the OpenVPN server listens on. Default is 1194. Use 443 to blend with HTTPS traffic.",
        directive_type="single",
        default="1194",
        example="1194",
        category="network",
    ),
    "dev": DirectiveSpec(
        name="dev",
        description="Virtual network device type. 'tun' creates a routed IP tunnel; 'tap' creates an Ethernet bridge tunnel.",
        directive_type="single",
        default="tun",
        allowed_values=["tun", "tap"],
        example="tun",
        category="network",
    ),
    "dev-node": DirectiveSpec(
        name="dev-node",
        description="Explicit name of the TUN/TAP device node. Useful when running multiple VPN instances.",
        directive_type="single",
        example="tun0",
        category="network",
    ),
    "server": DirectiveSpec(
        name="server",
        description="Shorthand for configuring the server-side VPN subnet. Specifies the IP address pool and netmask for clients.",
        directive_type="single",
        example="10.8.0.0 255.255.255.0",
        category="network",
    ),
    "server-ipv6": DirectiveSpec(
        name="server-ipv6",
        description="Configure an IPv6 address pool for the server in CIDR notation.",
        directive_type="single",
        example="2001:db8::/64",
        category="network",
    ),
    "topology": DirectiveSpec(
        name="topology",
        description="Specifies the VPN topology. 'subnet' is recommended for tun mode; 'net30' is the legacy default.",
        directive_type="single",
        default="net30",
        allowed_values=["net30", "p2p", "subnet"],
        example="subnet",
        category="network",
    ),
    "ifconfig": DirectiveSpec(
        name="ifconfig",
        description="Set the local and remote endpoints of the VPN tunnel (used in p2p mode).",
        directive_type="single",
        example="10.8.0.1 10.8.0.2",
        category="network",
    ),
    "ifconfig-pool": DirectiveSpec(
        name="ifconfig-pool",
        description="Set the dynamic IP address pool for connecting clients.",
        directive_type="single",
        example="10.8.0.4 10.8.0.251",
        category="network",
    ),
    "ifconfig-pool-persist": DirectiveSpec(
        name="ifconfig-pool-persist",
        description="Persist client IP address assignments to a file so they are reused across server restarts.",
        directive_type="single",
        default="/var/log/openvpn/ipp.txt",
        example="/var/log/openvpn/ipp.txt",
        category="network",
    ),
    "push": DirectiveSpec(
        name="push",
        description="Push a configuration option to the client. Common examples: 'redirect-gateway def1', 'route 192.168.0.0 255.255.0.0', 'dhcp-option DNS 8.8.8.8'.",
        directive_type="multi",
        example='"redirect-gateway def1 bypass-dhcp"',
        category="network",
    ),
    "route": DirectiveSpec(
        name="route",
        description="Add a route to the server-side routing table after the tunnel is established.",
        directive_type="multi",
        example="192.168.0.0 255.255.0.0",
        category="network",
    ),
    "route-gateway": DirectiveSpec(
        name="route-gateway",
        description="Specify the default gateway to use for routes pushed to clients.",
        directive_type="single",
        example="10.8.0.1",
        category="network",
    ),
    "client-to-client": DirectiveSpec(
        name="client-to-client",
        description="Allow VPN clients to communicate directly with each other (traffic stays in the VPN).",
        directive_type="flag",
        category="network",
    ),
    "duplicate-cn": DirectiveSpec(
        name="duplicate-cn",
        description="Allow multiple clients to connect simultaneously with the same certificate common name. Not recommended for production.",
        directive_type="flag",
        category="network",
    ),
    "max-clients": DirectiveSpec(
        name="max-clients",
        description="Maximum number of clients that can connect simultaneously.",
        directive_type="single",
        default="100",
        example="100",
        category="network",
    ),
    # ── Cryptography ─────────────────────────────────────────────────────────
    "ca": DirectiveSpec(
        name="ca",
        description="Path to the Certificate Authority (CA) certificate file.",
        directive_type="single",
        example="/etc/openvpn/ca.crt",
        category="crypto",
    ),
    "cert": DirectiveSpec(
        name="cert",
        description="Path to the server's certificate file, signed by the CA.",
        directive_type="single",
        example="/etc/openvpn/server.crt",
        category="crypto",
    ),
    "key": DirectiveSpec(
        name="key",
        description="Path to the server's private key file. Keep this secret.",
        directive_type="single",
        example="/etc/openvpn/server.key",
        category="crypto",
    ),
    "dh": DirectiveSpec(
        name="dh",
        description="Path to the Diffie-Hellman parameters file. Used for perfect forward secrecy with static-key cipher suites.",
        directive_type="single",
        example="/etc/openvpn/dh2048.pem",
        category="crypto",
    ),
    "tls-auth": DirectiveSpec(
        name="tls-auth",
        description="Add an extra HMAC authentication layer on top of TLS to prevent DoS attacks and port scanning. Key direction must be set (0 on server, 1 on client).",
        directive_type="single",
        example="/etc/openvpn/ta.key 0",
        category="crypto",
    ),
    "tls-crypt": DirectiveSpec(
        name="tls-crypt",
        description="Encrypt and authenticate all TLS control channel packets. Stronger than tls-auth; prevents client identification without the shared key.",
        directive_type="single",
        example="/etc/openvpn/ta.key",
        category="crypto",
    ),
    "tls-version-min": DirectiveSpec(
        name="tls-version-min",
        description="Minimum TLS version to accept. Setting to '1.2' is recommended to disallow insecure older protocols.",
        directive_type="single",
        default="1.0",
        allowed_values=["1.0", "1.1", "1.2", "1.3"],
        example="1.2",
        category="crypto",
    ),
    "cipher": DirectiveSpec(
        name="cipher",
        description="Data channel cipher algorithm. AES-256-GCM is recommended for modern clients.",
        directive_type="single",
        default="BF-CBC",
        example="AES-256-GCM",
        category="crypto",
        deprecated=False,
    ),
    "data-ciphers": DirectiveSpec(
        name="data-ciphers",
        description="Colon-separated list of acceptable data channel ciphers (OpenVPN 2.5+). The first mutually supported cipher is negotiated.",
        directive_type="single",
        example="AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305",
        category="crypto",
    ),
    "auth": DirectiveSpec(
        name="auth",
        description="HMAC digest algorithm used to authenticate data channel packets and (if using tls-auth) control channel packets.",
        directive_type="single",
        default="SHA1",
        example="SHA256",
        category="crypto",
    ),
    "crl-verify": DirectiveSpec(
        name="crl-verify",
        description="Path to the Certificate Revocation List (CRL). Clients whose certificates appear in the CRL are denied access.",
        directive_type="single",
        example="/etc/openvpn/crl.pem",
        category="crypto",
    ),
    "verify-client-cert": DirectiveSpec(
        name="verify-client-cert",
        description="Controls whether client certificates are required. 'none' disables client cert requirement (use with username/password auth).",
        directive_type="single",
        allowed_values=["none", "optional", "require"],
        example="require",
        category="crypto",
    ),
    # ── Authentication ────────────────────────────────────────────────────────
    "auth-user-pass-verify": DirectiveSpec(
        name="auth-user-pass-verify",
        description="Script or plugin to use for username/password authentication. The script receives credentials via a temp file or stdin.",
        directive_type="single",
        example="/etc/openvpn/checkpsw.sh via-env",
        category="auth",
    ),
    "username-as-common-name": DirectiveSpec(
        name="username-as-common-name",
        description="Use the authenticated username as the client's common name instead of the certificate CN. Useful with PAM auth.",
        directive_type="flag",
        category="auth",
    ),
    "plugin": DirectiveSpec(
        name="plugin",
        description="Load an OpenVPN plugin. Commonly used for PAM authentication (openvpn-plugin-auth-pam.so).",
        directive_type="multi",
        example="/usr/lib/x86_64-linux-gnu/openvpn/plugins/openvpn-plugin-auth-pam.so openvpn",
        category="auth",
    ),
    "client-config-dir": DirectiveSpec(
        name="client-config-dir",
        description="Directory of per-client configuration files (CCD). Used to assign static IPs and push specific routes to individual clients.",
        directive_type="single",
        example="/etc/openvpn/ccd",
        category="auth",
    ),
    # ── Logging & Management ──────────────────────────────────────────────────
    "log": DirectiveSpec(
        name="log",
        description="Write logging output to this file. Each restart truncates the log.",
        directive_type="single",
        example="/var/log/openvpn/openvpn.log",
        category="logging",
    ),
    "log-append": DirectiveSpec(
        name="log-append",
        description="Write logging output to this file. Output is appended across restarts.",
        directive_type="single",
        example="/var/log/openvpn/openvpn.log",
        category="logging",
    ),
    "status": DirectiveSpec(
        name="status",
        description="Write a status file showing current client connections. The optional second argument is the update interval in seconds.",
        directive_type="single",
        example="/var/log/openvpn/openvpn-status.log 30",
        category="logging",
    ),
    "verb": DirectiveSpec(
        name="verb",
        description="Logging verbosity level. 0=silent, 3=normal, 9=maximum (for debugging only).",
        directive_type="single",
        default="3",
        allowed_values=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
        example="3",
        category="logging",
    ),
    "mute": DirectiveSpec(
        name="mute",
        description="Silence repeated log messages of the same type after N occurrences.",
        directive_type="single",
        default="20",
        example="20",
        category="logging",
    ),
    "management": DirectiveSpec(
        name="management",
        description="Enable the OpenVPN management interface on the specified address and port.",
        directive_type="single",
        example="127.0.0.1 7505",
        category="logging",
    ),
    # ── Connection behaviour ───────────────────────────────────────────────────
    "keepalive": DirectiveSpec(
        name="keepalive",
        description="Send a ping every N seconds and restart if no response received within M seconds. Example: 'keepalive 10 120'.",
        directive_type="single",
        default="10 120",
        example="10 120",
        category="connection",
    ),
    "inactive": DirectiveSpec(
        name="inactive",
        description="Disconnect a client after N seconds of inactivity.",
        directive_type="single",
        example="3600",
        category="connection",
    ),
    "ping": DirectiveSpec(
        name="ping",
        description="Send a ping to the remote peer if no data has been sent for N seconds.",
        directive_type="single",
        example="10",
        category="connection",
    ),
    "ping-restart": DirectiveSpec(
        name="ping-restart",
        description="Restart the tunnel if no ping is received from the remote peer within N seconds.",
        directive_type="single",
        example="120",
        category="connection",
    ),
    "reneg-sec": DirectiveSpec(
        name="reneg-sec",
        description="Renegotiate the data channel key after N seconds. Default is 3600.",
        directive_type="single",
        default="3600",
        example="3600",
        category="connection",
    ),
    "comp-lzo": DirectiveSpec(
        name="comp-lzo",
        description="Enable LZO compression on the VPN link. Deprecated in favour of compress.",
        directive_type="single",
        default="adaptive",
        allowed_values=["yes", "no", "adaptive"],
        example="no",
        category="connection",
        deprecated=True,
    ),
    "compress": DirectiveSpec(
        name="compress",
        description="Enable compression. Consider security implications (VORACLE attack) before enabling.",
        directive_type="single",
        allowed_values=["lzo", "lz4", "lz4-v2", "stub", "stub-v2"],
        example="lz4",
        category="connection",
    ),
    # ── Privilege & Process ────────────────────────────────────────────────────
    "user": DirectiveSpec(
        name="user",
        description="After initialisation, drop privileges to this non-privileged user.",
        directive_type="single",
        default="nobody",
        example="nobody",
        category="security",
    ),
    "group": DirectiveSpec(
        name="group",
        description="After initialisation, drop privileges to this group.",
        directive_type="single",
        default="nogroup",
        example="nogroup",
        category="security",
    ),
    "persist-key": DirectiveSpec(
        name="persist-key",
        description="Do not re-read key files across SIGUSR1 or ping-restart restarts. Required when running as an unprivileged user.",
        directive_type="flag",
        category="security",
    ),
    "persist-tun": DirectiveSpec(
        name="persist-tun",
        description="Do not close and reopen the TUN/TAP device across SIGUSR1 or ping-restart restarts.",
        directive_type="flag",
        category="security",
    ),
    "chroot": DirectiveSpec(
        name="chroot",
        description="Chroot into this directory after initialisation for additional isolation.",
        directive_type="single",
        example="/var/empty",
        category="security",
    ),
    "daemon": DirectiveSpec(
        name="daemon",
        description="Run OpenVPN as a daemon process. When using systemd, this is typically not needed.",
        directive_type="single",
        example="openvpn",
        category="process",
    ),
    "writepid": DirectiveSpec(
        name="writepid",
        description="Write the OpenVPN process ID to this file.",
        directive_type="single",
        example="/run/openvpn/server.pid",
        category="process",
    ),
    "nice": DirectiveSpec(
        name="nice",
        description="Process scheduling priority (-20=highest, 19=lowest).",
        directive_type="single",
        example="0",
        category="process",
    ),
    "script-security": DirectiveSpec(
        name="script-security",
        description="Controls execution of external scripts and programs. Level 2 allows user-defined scripts.",
        directive_type="single",
        default="1",
        allowed_values=["0", "1", "2", "3"],
        example="2",
        category="security",
    ),
}


def get_all_directives() -> list[DirectiveSpec]:
    return list(DIRECTIVES.values())


def get_directive(name: str) -> DirectiveSpec | None:
    return DIRECTIVES.get(name)
