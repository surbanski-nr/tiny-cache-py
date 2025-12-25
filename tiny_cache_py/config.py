from typing import Tuple

from .errors import CacheValidationError


def parse_server_address(server_address: str, use_ssl: bool) -> Tuple[str, int, bool]:
    address = server_address.strip()
    if not address:
        raise CacheValidationError("Server address cannot be empty")

    if address.startswith("grpc://"):
        address = address[len("grpc://") :]
        use_ssl = False
    elif address.startswith("grpcs://"):
        address = address[len("grpcs://") :]
        use_ssl = True

    if address.startswith("["):
        bracket_end = address.find("]")
        if bracket_end == -1:
            raise CacheValidationError("Invalid IPv6 server address")
        host = address[1:bracket_end]
        port_part = address[bracket_end + 1 :]
        if not port_part:
            port = 50051
        elif port_part.startswith(":"):
            port = int(port_part[1:])
        else:
            raise CacheValidationError("Invalid IPv6 server address")
    else:
        if ":" in address:
            host_part, port_part = address.rsplit(":", 1)
            host = host_part
            port = int(port_part)
        else:
            host = address
            port = 50051

    if not host:
        raise CacheValidationError("Server host cannot be empty")
    if not (1 <= port <= 65535):
        raise CacheValidationError("Server port must be between 1 and 65535")

    return host, port, use_ssl

