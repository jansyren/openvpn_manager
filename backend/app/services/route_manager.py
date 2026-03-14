"""
Manages IP routes between VPN tun interfaces using the `ip route` command.
"""
import ipaddress

from app.core.exceptions import RemoteExecutionError, ValidationError
from app.services.remote.base import Executor

_IP = "/sbin/ip"
_IP_ALT = "/usr/sbin/ip"
_IPTABLES = "/usr/sbin/iptables"


def _ip_bin() -> str:
    return _IP


async def get_live_routes(executor: Executor) -> list[str]:
    result = await executor.run_command([_ip_bin(), "route", "show"], timeout=10.0)
    result.raise_on_error("ip route show")
    return [line for line in result.stdout.splitlines() if line.strip()]


async def apply_route(
    executor: Executor,
    destination_network: str,
    dest_tun: str,
    metric: int = 0,
) -> None:
    _validate_network(destination_network)
    _validate_tun(dest_tun)

    cmd = [_ip_bin(), "route", "add", destination_network, "dev", dest_tun]
    if metric > 0:
        cmd += ["metric", str(metric)]

    result = await executor.run_command(cmd, timeout=10.0)
    # Exit 2 = "RTNETLINK answers: File exists" — idempotent
    if result.returncode not in (0, 2):
        result.raise_on_error(f"ip route add {destination_network}")


async def remove_route(executor: Executor, destination_network: str, dest_tun: str) -> None:
    _validate_network(destination_network)
    _validate_tun(dest_tun)

    result = await executor.run_command(
        [_ip_bin(), "route", "del", destination_network, "dev", dest_tun],
        timeout=10.0,
    )
    # Exit 2 = route not found — treat as success (idempotent)
    if result.returncode not in (0, 2):
        result.raise_on_error(f"ip route del {destination_network}")


async def add_iptables_forward_rule(
    executor: Executor,
    source_tun: str,
    dest_tun: str,
) -> None:
    """Allow forwarding between two tun interfaces."""
    _validate_tun(source_tun)
    _validate_tun(dest_tun)

    for in_if, out_if in [(source_tun, dest_tun), (dest_tun, source_tun)]:
        result = await executor.run_command(
            [_IPTABLES, "-C", "FORWARD", "-i", in_if, "-o", out_if, "-j", "ACCEPT"],
            timeout=10.0,
        )
        if result.returncode != 0:
            # Rule doesn't exist — add it
            await executor.run_command(
                [_IPTABLES, "-A", "FORWARD", "-i", in_if, "-o", out_if, "-j", "ACCEPT"],
                timeout=10.0,
            )


def _validate_network(network: str) -> None:
    try:
        ipaddress.IPv4Network(network, strict=False)
    except ValueError as exc:
        raise ValidationError(f"Invalid network: {network}") from exc


def _validate_tun(tun: str) -> None:
    import re

    if not re.match(r"^tun\d+$", tun):
        raise ValidationError(f"Invalid tun interface name: {tun!r}")
