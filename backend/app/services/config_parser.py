"""
OpenVPN configuration file parser.

Handles:
- Key-value directives: 'directive value'
- Flag directives: 'directive' (no value)
- Repeatable directives: multiple lines with the same key
- Inline data blocks: <tag> ... </tag>
- Comment lines: # or ;
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedConfig:
    """Structured representation of an OpenVPN .conf file."""

    # Regular directives; multi-value ones stored as lists
    directives: dict[str, Any] = field(default_factory=dict)
    # Inline blocks: ca, cert, key, tls-auth, tls-crypt, dh, etc.
    inline_blocks: dict[str, str] = field(default_factory=dict)
    # Preserve comment lines and blank lines for round-trip fidelity
    _raw_lines: list[str] = field(default_factory=list, repr=False)


# Directives that can appear multiple times (stored as list)
_MULTI_DIRECTIVES = frozenset(
    [
        "push",
        "route",
        "plugin",
        "route-ipv6",
        "iroute",
        "iroute-ipv6",
        "ifconfig-push",
    ]
)

# Directives that take no value (flags)
_FLAG_DIRECTIVES = frozenset(
    [
        "client-to-client",
        "duplicate-cn",
        "persist-key",
        "persist-tun",
        "username-as-common-name",
        "topology-subnet",  # handled via topology directive
        "nobind",
        "float",
        "mlock",
    ]
)


def parse_config(content: str) -> ParsedConfig:
    """Parse OpenVPN config file content into a structured object."""
    result = ParsedConfig()
    result._raw_lines = content.splitlines(keepends=True)

    lines = iter(result._raw_lines)
    current_block_tag: str | None = None
    current_block_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue

        # Detect inline block start
        if stripped.startswith("<") and not stripped.startswith("</"):
            tag = stripped[1:-1].strip()
            current_block_tag = tag
            current_block_lines = []
            continue

        # Detect inline block end
        if stripped.startswith("</") and current_block_tag:
            result.inline_blocks[current_block_tag] = "\n".join(current_block_lines)
            current_block_tag = None
            current_block_lines = []
            continue

        # Inside a block
        if current_block_tag is not None:
            current_block_lines.append(stripped)
            continue

        # Regular directive — split on first whitespace
        parts = stripped.split(None, 1)
        directive = parts[0].lower()
        value = parts[1] if len(parts) > 1 else None

        if directive in _MULTI_DIRECTIVES:
            if directive not in result.directives:
                result.directives[directive] = []
            if value is not None:
                result.directives[directive].append(value)
        elif value is None or directive in _FLAG_DIRECTIVES:
            result.directives[directive] = True  # flag
        else:
            result.directives[directive] = value

    return result


def serialize_config(config: ParsedConfig) -> str:
    """Serialize a ParsedConfig back to .conf file format."""
    lines: list[str] = []

    for key, value in config.directives.items():
        if value is True:
            lines.append(key)
        elif isinstance(value, list):
            for item in value:
                lines.append(f"{key} {item}")
        else:
            lines.append(f"{key} {value}")

    for tag, content in config.inline_blocks.items():
        lines.append(f"<{tag}>")
        lines.append(content)
        lines.append(f"</{tag}>")

    return "\n".join(lines) + "\n"
