from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

import httpx

from app.core.config import get_settings

_cached_rates: dict[str, object] | None = None
_cache_expires_at: datetime | None = None


def _decimal_text(element: ElementTree.Element, field: str) -> Decimal:
    value = (element.findtext(field) or "").strip().replace(",", ".")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Geçersiz {field} değeri") from exc


async def get_exchange_rates(force_refresh: bool = False) -> dict[str, object]:
    global _cached_rates, _cache_expires_at
    settings = get_settings()
    now = datetime.now(UTC)
    if not force_refresh and _cached_rates and _cache_expires_at and now < _cache_expires_at:
        return {**_cached_rates, "cached": True}

    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            response = await client.get(settings.exchange_rate_url)
            response.raise_for_status()
        root = ElementTree.fromstring(response.content)
        currencies = {item.attrib.get("CurrencyCode"): item for item in root.findall("Currency")}
        rates = {
            "base": "TRY",
            "usd_try": str(_decimal_text(currencies["USD"], "ForexSelling")),
            "eur_try": str(_decimal_text(currencies["EUR"], "ForexSelling")),
            "published_at": root.attrib.get("Tarih") or root.attrib.get("Date") or now.date().isoformat(),
            "fetched_at": now.isoformat(),
            "source": "TCMB",
            "cached": False,
            "stale": False,
        }
        _cached_rates = rates
        _cache_expires_at = now + timedelta(minutes=settings.exchange_rate_cache_minutes)
        return rates
    except (httpx.HTTPError, ElementTree.ParseError, KeyError, ValueError):
        if _cached_rates:
            return {**_cached_rates, "cached": True, "stale": True}
        return {
            "base": "TRY",
            "usd_try": str(settings.exchange_rate_fallback_usd),
            "eur_try": str(settings.exchange_rate_fallback_eur),
            "published_at": "",
            "fetched_at": now.isoformat(),
            "source": "Yedek kur",
            "cached": False,
            "stale": True,
        }
