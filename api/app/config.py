from __future__ import annotations

import os
import ssl as ssl_lib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql://drivebook:drivebook@127.0.0.1:5433/drivebook?sslmode=disable",
    )
    # asyncpg wants postgresql:// without +asyncpg
    api_host: str = "127.0.0.1"
    api_port: int = 8100
    brand_name: str = "PermisPro"
    city: str = "Chișinău"
    country: str = "MD"
    deposit_default_cents: int = 10000  # 100 MDL stub
    require_deposit: bool = False

    class Config:
        env_prefix = "DRIVEBOOK_"
        extra = "ignore"


settings = Settings()


def asyncpg_kwargs(dsn: str | None = None) -> dict:
    """Build kwargs for ``asyncpg.connect`` / ``asyncpg.create_pool``.

    ``dsn`` overrides ``settings.database_url`` when given; otherwise the
    single source of truth is ``settings.database_url``, which already reads
    the ``DATABASE_URL`` env var (Neon/Render) with a local fallback.

    Managed Postgres (Neon) hands out URLs like
    ``postgresql://user:pass@host/db?sslmode=require``. asyncpg's parsing of
    the libpq ``sslmode`` query parameter is version-dependent, so we strip it
    (and other libpq-only ssl params) from the DSN and translate it into an
    explicit ``ssl`` argument. Same code path works locally (sslmode=disable)
    and on Neon (sslmode=require).
    """
    dsn = dsn or settings.database_url
    parts = urlsplit(dsn)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    sslmode = query.pop("sslmode", None)
    # libpq-only params asyncpg does not accept as query args
    for k in ("sslrootcert", "sslcert", "sslkey", "sslpassword", "channel_binding"):
        query.pop(k, None)
    clean_dsn = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )

    kwargs: dict = {"dsn": clean_dsn}
    if sslmode is None:
        return kwargs
    mode = sslmode.lower()
    if mode == "disable":
        kwargs["ssl"] = False
    elif mode in ("allow", "prefer", "require"):
        # encrypt without cert/hostname verification (libpq `require` semantics)
        ctx = ssl_lib.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl_lib.CERT_NONE
        kwargs["ssl"] = ctx
    elif mode in ("verify-ca", "verify-full"):
        kwargs["ssl"] = ssl_lib.create_default_context()
    else:
        kwargs["ssl"] = True
    return kwargs
