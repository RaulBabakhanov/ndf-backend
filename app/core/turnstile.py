import httpx
from fastapi import HTTPException

from app.core.config import get_settings

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str, remote_ip: str | None) -> None:
    settings = get_settings()
    if not settings.turnstile_secret_key:
        raise HTTPException(status_code=503, detail="Bot doğrulama sistemi yapılandırılmamış.")

    payload = {"secret": settings.turnstile_secret_key, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(VERIFY_URL, data=payload)
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Bot doğrulama servisine ulaşılamadı.") from exc

    if not result.get("success"):
        raise HTTPException(status_code=400, detail="Bot doğrulaması başarısız oldu. Lütfen tekrar deneyin.")
    expected_hostnames = {
        hostname.strip()
        for hostname in settings.turnstile_expected_hostname.split(",")
        if hostname.strip()
    }
    if expected_hostnames and result.get("hostname") not in expected_hostnames:
        raise HTTPException(status_code=400, detail="Bot doğrulaması geçersiz alan adından geldi.")
