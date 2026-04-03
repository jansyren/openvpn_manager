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
- mutually_exclusive_with: list of directive names that cannot be used together with this one
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
    mutually_exclusive_with: list[str] = []


DIRECTIVES: dict[str, DirectiveSpec] = {
    # ── Network ──────────────────────────────────────────────────────────────
    "proto": DirectiveSpec(
        name="proto",
        description="Network protocol used for the VPN tunnel. 'udp' is recommended for performance; 'tcp' may be needed to traverse firewalls that block UDP.",
        directive_type="single",
        default="udp",
        allowed_values=["udp", "udp4", "udp6", "tcp", "tcp4", "tcp6"],
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
        description="Virtual network device name. Use 'tun' or 'tun0', 'tun1' etc. for a routed IP tunnel, or 'tap' / 'tap0' for an Ethernet bridge. When using a numbered name, set dev-type explicitly.",
        directive_type="single",
        default="tun",
        allowed_values=None,
        example="tun1",
        category="network",
    ),
    "dev-type": DirectiveSpec(
        name="dev-type",
        description="Device type when using a specific device name (e.g. 'tun0'). Required when the dev name does not start with 'tun' or 'tap'.",
        directive_type="single",
        allowed_values=["tun", "tap"],
        example="tun",
        category="network",
    ),
    "dev-node": DirectiveSpec(
        name="dev-node",
        description="Explicit path to the TUN/TAP device node. Useful on platforms where the default node path differs.",
        directive_type="single",
        example="/dev/net/tun",
        category="network",
    ),
    "server": DirectiveSpec(
        name="server",
        description="Convenience macro for server-mode configuration. Sets the VPN subnet and configures ifconfig, ifconfig-pool, route and push directives automatically. Format: 'network netmask' (e.g. '10.8.0.0 255.255.255.0'). Do not combine with ifconfig or ifconfig-pool.",
        directive_type="single",
        example="10.8.0.0 255.255.255.0",
        category="network",
        mutually_exclusive_with=["ifconfig", "ifconfig-pool"],
    ),
    "server-ipv6": DirectiveSpec(
        name="server-ipv6",
        description="Convenience macro that configures an IPv6 address pool in CIDR notation. Expands to ifconfig-ipv6, ifconfig-ipv6-pool, and pushes tun-ipv6 to clients.",
        directive_type="single",
        example="2001:db8::/64",
        category="network",
    ),
    "topology": DirectiveSpec(
        name="topology",
        description="VPN topology for tun devices. 'subnet' is strongly recommended — it assigns each client a real subnet address. 'net30' (legacy default) wastes IPs. 'p2p' is for point-to-point links only.",
        directive_type="single",
        default="net30",
        allowed_values=["net30", "p2p", "subnet"],
        example="subnet",
        category="network",
    ),
    "ifconfig": DirectiveSpec(
        name="ifconfig",
        description="Manually set the local and remote VPN endpoint addresses. Use when not using the 'server' macro.",
        directive_type="single",
        example="10.8.0.1 10.8.0.2",
        category="network",
        mutually_exclusive_with=["server"],
    ),
    "ifconfig-pool": DirectiveSpec(
        name="ifconfig-pool",
        description="Manually define the dynamic IP pool for clients. Use when not using the 'server' macro. Format: 'start-IP end-IP [netmask]'.",
        directive_type="single",
        example="10.8.0.4 10.8.0.251",
        category="network",
        mutually_exclusive_with=["server"],
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
        description="Push a configuration option to connecting clients. Each value must be quoted. Common examples: '\"redirect-gateway def1 bypass-dhcp\"', '\"dhcp-option DNS 8.8.8.8\"', '\"route 192.168.1.0 255.255.255.0\"'.",
        directive_type="multi",
        example='"redirect-gateway def1 bypass-dhcp"',
        category="network",
    ),
    "route": DirectiveSpec(
        name="route",
        description="Add a route to the server-side routing table after tunnel establishment. Format: 'network [netmask [gateway [metric]]]'.",
        directive_type="multi",
        example="192.168.0.0 255.255.0.0",
        category="network",
    ),
    "route-gateway": DirectiveSpec(
        name="route-gateway",
        description="Default gateway for routes added by --route. Use an explicit IP address or 'dhcp' to use the DHCP-assigned gateway.",
        directive_type="single",
        example="10.8.0.1",
        category="network",
    ),
    "client-to-client": DirectiveSpec(
        name="client-to-client",
        description="Allow VPN clients to communicate directly with each other without leaving the VPN.",
        directive_type="flag",
        category="network",
    ),
    "duplicate-cn": DirectiveSpec(
        name="duplicate-cn",
        description="Allow multiple simultaneous connections from clients sharing the same certificate CN. Not recommended for production — use username-as-common-name instead.",
        directive_type="flag",
        category="network",
    ),
    "max-clients": DirectiveSpec(
        name="max-clients",
        description="Maximum number of clients that may connect simultaneously.",
        directive_type="single",
        default="100",
        example="100",
        category="network",
    ),
    # ── Cryptography ─────────────────────────────────────────────────────────
    "ca": DirectiveSpec(
        name="ca",
        description="Path to the Certificate Authority (CA) certificate file. All client certificates must be signed by this CA.",
        directive_type="single",
        example="/etc/openvpn/ca.crt",
        category="crypto",
    ),
    "cert": DirectiveSpec(
        name="cert",
        description="Path to the server's local certificate file, signed by the CA.",
        directive_type="single",
        example="/etc/openvpn/server.crt",
        category="crypto",
    ),
    "key": DirectiveSpec(
        name="key",
        description="Path to the server's private key file. Must be kept secret and not world-readable.",
        directive_type="single",
        example="/etc/openvpn/server.key",
        category="crypto",
    ),
    "dh": DirectiveSpec(
        name="dh",
        description="Path to the Diffie-Hellman parameters file (required for TLS server mode). Set to 'none' to disable DH and use ECDH only (requires OpenSSL 1.0.1+ or mbed TLS 2.0+). Generate with: openssl dhparam -out dh2048.pem 2048",
        directive_type="single",
        example="/etc/openvpn/dh.pem",
        category="crypto",
    ),
    "tls-auth": DirectiveSpec(
        name="tls-auth",
        description="Add HMAC authentication to all TLS handshake packets to protect against DoS attacks and port scanning. Format: 'keyfile [direction]' where direction is 0 on the server and 1 on clients. Cannot be used together with tls-crypt.",
        directive_type="single",
        example="/etc/openvpn/ta.key 0",
        category="crypto",
        mutually_exclusive_with=["tls-crypt"],
    ),
    "tls-crypt": DirectiveSpec(
        name="tls-crypt",
        description="Encrypt and authenticate all TLS control channel packets using a pre-shared key. Stronger than tls-auth — also hides the certificate. No direction parameter needed. Cannot be used together with tls-auth.",
        directive_type="single",
        example="/etc/openvpn/ta.key",
        category="crypto",
        mutually_exclusive_with=["tls-auth"],
    ),
    "tls-version-min": DirectiveSpec(
        name="tls-version-min",
        description="Minimum TLS version to accept. '1.2' is the recommended minimum. '1.0' and '1.1' are insecure and should not be used.",
        directive_type="single",
        default="1.2",
        allowed_values=["1.0", "1.1", "1.2", "1.3"],
        example="1.2",
        category="crypto",
    ),
    "cipher": DirectiveSpec(
        name="cipher",
        description="Data channel cipher (DEPRECATED for TLS mode — use data-ciphers instead). In TLS mode with OpenVPN 2.6+, this option is ignored. Still useful for compatibility with peers older than 2.6.0.",
        directive_type="single",
        default="BF-CBC",
        example="AES-256-GCM",
        category="crypto",
        deprecated=True,
    ),
    "data-ciphers": DirectiveSpec(
        name="data-ciphers",
        description="Colon-separated list of acceptable data channel ciphers (OpenVPN 2.5+). The first mutually supported cipher is negotiated. Supersedes 'cipher' in TLS mode.",
        directive_type="single",
        example="AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305",
        category="crypto",
    ),
    "auth": DirectiveSpec(
        name="auth",
        description="HMAC digest algorithm for data channel packet authentication. Ignored when using an AEAD cipher (e.g. AES-GCM) for the data channel. Also used for tls-auth control channel packets. Set to 'none' to disable (not recommended).",
        directive_type="single",
        default="SHA1",
        allowed_values=["SHA1", "SHA256", "SHA384", "SHA512", "MD5", "none"],
        example="SHA256",
        category="crypto",
    ),
    "crl-verify": DirectiveSpec(
        name="crl-verify",
        description="Path to the Certificate Revocation List (CRL) file. Clients whose certificates appear in the CRL are denied access.",
        directive_type="single",
        example="/etc/openvpn/crl.pem",
        category="crypto",
    ),
    "verify-client-cert": DirectiveSpec(
        name="verify-client-cert",
        description="Controls whether client certificates are required. 'require' (default) mandates a valid cert. 'optional' accepts clients without a cert. 'none' disables client cert checking — must be combined with username/password authentication.",
        directive_type="single",
        allowed_values=["none", "optional", "require"],
        example="require",
        category="crypto",
    ),
    # ── Authentication ────────────────────────────────────────────────────────
    "auth-user-pass-verify": DirectiveSpec(
        name="auth-user-pass-verify",
        description="Script or plugin for username/password authentication. Format: 'script method' where method is 'via-env' (credentials in environment) or 'via-file' (credentials in a temp file). Requires script-security 2 or higher.",
        directive_type="single",
        example="/etc/openvpn/checkpsw.sh via-env",
        category="auth",
    ),
    "username-as-common-name": DirectiveSpec(
        name="username-as-common-name",
        description="Use the authenticated username as the client's common name instead of the certificate CN. Useful with PAM or script-based authentication.",
        directive_type="flag",
        category="auth",
    ),
    "plugin": DirectiveSpec(
        name="plugin",
        description="Load an OpenVPN plugin module. Commonly used for PAM authentication. Example: '/usr/lib/x86_64-linux-gnu/openvpn/plugins/openvpn-plugin-auth-pam.so openvpn'",
        directive_type="multi",
        example="/usr/lib/x86_64-linux-gnu/openvpn/plugins/openvpn-plugin-auth-pam.so openvpn",
        category="auth",
    ),
    "client-config-dir": DirectiveSpec(
        name="client-config-dir",
        description="Directory containing per-client configuration files (CCD). Files are named after the client's common name and can assign static IPs or push specific routes to individual clients.",
        directive_type="single",
        example="/etc/openvpn/ccd",
        category="auth",
    ),
    "ccd-exclusive": DirectiveSpec(
        name="ccd-exclusive",
        description="Require that every connecting client has a matching file in the client-config-dir. Clients without a CCD file are denied access. Requires client-config-dir to be set.",
        directive_type="flag",
        category="auth",
    ),
    # ── Logging & Management ──────────────────────────────────────────────────
    "log": DirectiveSpec(
        name="log",
        description="Write all log output to this file. The file is truncated on each restart. Cannot be used together with log-append.",
        directive_type="single",
        example="/var/log/openvpn/openvpn.log",
        category="logging",
        mutually_exclusive_with=["log-append"],
    ),
    "log-append": DirectiveSpec(
        name="log-append",
        description="Write all log output to this file. Output is appended on each restart (not truncated). Cannot be used together with log.",
        directive_type="single",
        example="/var/log/openvpn/openvpn.log",
        category="logging",
        mutually_exclusive_with=["log"],
    ),
    "status": DirectiveSpec(
        name="status",
        description="Write a status file showing current client connections and traffic statistics. Optional second parameter is the update interval in seconds (default: every write). Example: '/var/log/openvpn/status.log 30'",
        directive_type="single",
        example="/var/log/openvpn/openvpn-status.log 30",
        category="logging",
    ),
    "verb": DirectiveSpec(
        name="verb",
        description="Logging verbosity. 0=silent, 3=normal operations, 5=verbose, 9=maximum debug output. Use 3 for production.",
        directive_type="single",
        default="3",
        allowed_values=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"],
        example="3",
        category="logging",
    ),
    "mute": DirectiveSpec(
        name="mute",
        description="Silence repeated log messages of the same type after N occurrences per 30 seconds.",
        directive_type="single",
        default="20",
        example="20",
        category="logging",
    ),
    "management": DirectiveSpec(
        name="management",
        description="Enable the management interface on the specified IP and port. Format: 'address port [password-file]'. Allows external tools to monitor and control the VPN. Example: '127.0.0.1 7505'",
        directive_type="single",
        example="127.0.0.1 7505",
        category="logging",
    ),
    # ── Connection behaviour ───────────────────────────────────────────────────
    "keepalive": DirectiveSpec(
        name="keepalive",
        description="Convenience macro: sends a ping every N seconds and restarts the tunnel if no response arrives within M seconds. Equivalent to setting both 'ping N' and 'ping-restart M'. Do not combine with ping or ping-restart.",
        directive_type="single",
        default="10 120",
        example="10 120",
        category="connection",
        mutually_exclusive_with=["ping", "ping-restart"],
    ),
    "inactive": DirectiveSpec(
        name="inactive",
        description="Disconnect a client after N seconds of inactivity (no data exchanged). Optional second parameter limits based on bytes transferred: 'inactive seconds [bytes]'.",
        directive_type="single",
        example="3600",
        category="connection",
    ),
    "ping": DirectiveSpec(
        name="ping",
        description="Send a ping to the remote peer every N seconds if no data has been sent. Used together with ping-restart or ping-exit. Use 'keepalive' as a convenient shorthand instead.",
        directive_type="single",
        example="10",
        category="connection",
        mutually_exclusive_with=["keepalive"],
    ),
    "ping-restart": DirectiveSpec(
        name="ping-restart",
        description="Restart the tunnel if no ping or data is received from the peer within N seconds. Cannot be used together with ping-exit or keepalive.",
        directive_type="single",
        example="120",
        category="connection",
        mutually_exclusive_with=["keepalive", "ping-exit"],
    ),
    "ping-exit": DirectiveSpec(
        name="ping-exit",
        description="Exit (rather than restart) if no ping or data is received from the peer within N seconds. Cannot be used together with ping-restart.",
        directive_type="single",
        example="120",
        category="connection",
        mutually_exclusive_with=["ping-restart"],
    ),
    "reneg-sec": DirectiveSpec(
        name="reneg-sec",
        description="Renegotiate the data channel key after N seconds. Default is 3600. Set to 0 to disable periodic renegotiation.",
        directive_type="single",
        default="3600",
        example="3600",
        category="connection",
    ),
    "comp-lzo": DirectiveSpec(
        name="comp-lzo",
        description="DEPRECATED — use 'compress' instead. Enable LZO compression. Note: compression has known security vulnerabilities (VORACLE attack). Consider disabling entirely.",
        directive_type="single",
        default="adaptive",
        allowed_values=["yes", "no", "adaptive"],
        example="no",
        category="connection",
        deprecated=True,
        mutually_exclusive_with=["compress"],
    ),
    "compress": DirectiveSpec(
        name="compress",
        description="DEPRECATED — compression has known security vulnerabilities (VORACLE attack) and is discouraged. If you must use it, 'stub' or 'stub-v2' disables compression while maintaining backward compatibility. Cannot be used with comp-lzo.",
        directive_type="single",
        allowed_values=["lzo", "lz4", "lz4-v2", "stub", "stub-v2", "migrate"],
        example="stub",
        category="connection",
        deprecated=True,
        mutually_exclusive_with=["comp-lzo"],
    ),
    "allow-compression": DirectiveSpec(
        name="allow-compression",
        description="Controls whether compression is allowed on this endpoint. 'no' prevents the peer from enabling compression (recommended for security). 'asym' allows receiving compressed but not sending. 'yes' allows both.",
        directive_type="single",
        allowed_values=["no", "asym", "yes"],
        example="no",
        category="connection",
    ),
    # ── Security & Privileges ────────────────────────────────────────────────
    "user": DirectiveSpec(
        name="user",
        description="Drop privileges to this user after initialisation. Combine with persist-key and persist-tun so restarts work correctly.",
        directive_type="single",
        default="nobody",
        example="nobody",
        category="security",
    ),
    "group": DirectiveSpec(
        name="group",
        description="Drop privileges to this group after initialisation.",
        directive_type="single",
        default="nogroup",
        example="nogroup",
        category="security",
    ),
    "persist-key": DirectiveSpec(
        name="persist-key",
        description="Do not re-read key files across SIGUSR1 or ping-restart restarts. Required when using user/group privilege dropping.",
        directive_type="flag",
        category="security",
    ),
    "persist-tun": DirectiveSpec(
        name="persist-tun",
        description="Do not close and reopen the TUN/TAP device across SIGUSR1 or ping-restart restarts. Reduces reconnection disruption.",
        directive_type="flag",
        category="security",
    ),
    "chroot": DirectiveSpec(
        name="chroot",
        description="Chroot into this directory after initialisation for additional process isolation. All required files must be accessible within the chroot.",
        directive_type="single",
        example="/var/empty",
        category="security",
    ),
    "script-security": DirectiveSpec(
        name="script-security",
        description="Controls execution of external scripts. 0=no scripts, 1=only built-in scripts, 2=allow user-defined scripts (needed for auth-user-pass-verify), 3=also allow passing environment variables to scripts.",
        directive_type="single",
        default="1",
        allowed_values=["0", "1", "2", "3"],
        example="2",
        category="security",
    ),
    # ── Process ────────────────────────────────────────────────────────────────
    "daemon": DirectiveSpec(
        name="daemon",
        description="Become a daemon process after initialisation. The optional value sets the program name reported to syslog (defaults to 'openvpn'). When managed by systemd, omit this directive.",
        directive_type="single",
        example="openvpn",
        category="process",
    ),
    "writepid": DirectiveSpec(
        name="writepid",
        description="Write the OpenVPN process ID to this file. Useful for init scripts.",
        directive_type="single",
        example="/run/openvpn/server.pid",
        category="process",
    ),
    "nice": DirectiveSpec(
        name="nice",
        description="Process scheduling niceness (-20=highest priority, 19=lowest). 0 is normal.",
        directive_type="single",
        example="0",
        category="process",
    ),
}


def get_all_directives() -> list[DirectiveSpec]:
    return list(DIRECTIVES.values())


def get_directive(name: str) -> DirectiveSpec | None:
    return DIRECTIVES.get(name)
