"""Proteções de destino para ferramentas que alteram bancos descartáveis."""

from ipaddress import ip_address
from urllib.parse import parse_qsl, urlsplit

_DESTINATION_OVERRIDE_PARAMETERS = frozenset({"dbname", "host", "hostaddr", "service"})


def ensure_loopback_database_url(url: str) -> None:
    """Recusa URLs cujo destino efetivo possa sair da máquina local."""
    parsed = urlsplit(url)
    query_parameters = {
        key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    }
    overrides = query_parameters & _DESTINATION_OVERRIDE_PARAMETERS
    if overrides:
        names = ", ".join(sorted(overrides))
        raise RuntimeError(
            f"refusing database URL with destination override parameter: {names}"
        )

    hostname = parsed.hostname
    if hostname is not None and hostname.lower() == "localhost":
        return

    try:
        address = ip_address(hostname or "")
    except ValueError:
        address = None

    if address is not None and address.is_loopback:
        return

    raise RuntimeError(
        f"refusing integration database operation on non-loopback host {hostname!r}"
    )
