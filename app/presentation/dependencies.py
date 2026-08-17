from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.infrastructure.database import get_session
from app.infrastructure.models import DealerModel
from app.infrastructure.repositories import SqlAlchemyDealerRepository

SessionDep = Annotated[AsyncSession, Depends(get_session)]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_dealer(session: SessionDep, token: Annotated[str, Depends(oauth2_scheme)]) -> DealerModel:
    credentials_error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Geçersiz veya süresi dolmuş oturum")
    try:
        dealer_id = int(decode_access_token(token))
    except (jwt.InvalidTokenError, ValueError):
        raise credentials_error from None
    dealer = await SqlAlchemyDealerRepository(session).get_by_id(dealer_id)
    if not dealer:
        raise credentials_error
    return dealer


CurrentDealer = Annotated[DealerModel, Depends(get_current_dealer)]
