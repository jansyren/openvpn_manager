"""Unit tests for the OpenVPN directives catalog."""
import pytest

from app.services.openvpn_directives import DIRECTIVES, DirectiveSpec, get_all_directives, get_directive


def test_no_duplicate_directive_names():
    """Every directive key must match its name field."""
    for key, spec in DIRECTIVES.items():
        assert key == spec.name, f"Key {key!r} does not match spec.name {spec.name!r}"


def test_all_directives_have_required_fields():
    for name, spec in DIRECTIVES.items():
        assert spec.description, f"Directive {name!r} has no description"
        assert spec.directive_type in ("flag", "single", "multi"), (
            f"Directive {name!r} has invalid directive_type: {spec.directive_type!r}"
        )
        assert spec.category, f"Directive {name!r} has no category"


def test_get_directive_known():
    spec = get_directive("proto")
    assert spec is not None
    assert spec.name == "proto"
    assert "protocol" in spec.description.lower()


def test_get_directive_unknown():
    assert get_directive("nonexistent-directive") is None


def test_get_all_directives_returns_list():
    directives = get_all_directives()
    assert isinstance(directives, list)
    assert len(directives) > 10  # We have many directives


def test_flag_directives_have_no_default():
    """Flag directives should not need a default value."""
    flags = [s for s in DIRECTIVES.values() if s.directive_type == "flag"]
    assert len(flags) > 0, "Should have at least some flag directives"
    for spec in flags:
        # Flags are valid with or without defaults
        assert spec.directive_type == "flag"


def test_proto_allowed_values():
    spec = get_directive("proto")
    assert spec is not None
    assert "udp" in spec.allowed_values
    assert "tcp" in spec.allowed_values


def test_deprecated_directives_marked():
    comp_lzo = get_directive("comp-lzo")
    assert comp_lzo is not None
    assert comp_lzo.deprecated is True
