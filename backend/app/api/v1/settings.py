"""Settings endpoints for automated mode configuration."""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from app.core.deps import DB
from app.db.models.app_setting import AppSetting

router = APIRouter()

# Default values
DEFAULT_AUTOMATED_MODE = False
DEFAULT_POLL_INTERVAL_SECONDS = 60
VALID_POLL_INTERVALS = [30, 60, 120, 300, 600]


class SettingsResponse(BaseModel):
    automated_mode: bool
    polling_interval_seconds: int

    model_config = {'from_attributes': True}


class SettingsUpdate(BaseModel):
    automated_mode: bool
    polling_interval_seconds: int = Field(ge=15, le=3600)


@router.get('/settings', response_model=SettingsResponse)
async def get_settings(db: DB):
    result = await db.execute(
        select(AppSetting).where(AppSetting.key.in_(['automated_mode', 'polling_interval_seconds']))
    )
    rows = result.scalars().all()

    settings_dict = {row.key: row.value for row in rows}

    automated_mode = settings_dict.get('automated_mode', str(DEFAULT_AUTOMATED_MODE)).lower() == 'true'
    poll_interval = int(settings_dict.get('polling_interval_seconds', str(DEFAULT_POLL_INTERVAL_SECONDS)))

    # Clamp interval to valid values
    valid_intervals = sorted([i for i in VALID_POLL_INTERVALS if i <= poll_interval])
    if valid_intervals:
        poll_interval = valid_intervals[-1]
    else:
        poll_interval = min(VALID_POLL_INTERVALS)

    return SettingsResponse(
        automated_mode=automated_mode,
        polling_interval_seconds=poll_interval,
    )


@router.put('/settings', response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate, db: DB):
    now = datetime.now(timezone.utc)

    # Update automated_mode
    existing = await db.scalar(
        select(AppSetting).where(AppSetting.key == 'automated_mode')
    )
    if existing:
        existing.value = str(payload.automated_mode).lower()
        existing.updated_at = now
    else:
        db.add(AppSetting(
            key='automated_mode',
            value=str(payload.automated_mode).lower(),
            updated_at=now,
        ))

    # Update polling_interval_seconds
    existing = await db.scalar(
        select(AppSetting).where(AppSetting.key == 'polling_interval_seconds')
    )
    if existing:
        existing.value = str(payload.polling_interval_seconds)
        existing.updated_at = now
    else:
        db.add(AppSetting(
            key='polling_interval_seconds',
            value=str(payload.polling_interval_seconds),
            updated_at=now,
        ))

    await db.commit()

    return SettingsResponse(
        automated_mode=payload.automated_mode,
        polling_interval_seconds=payload.polling_interval_seconds,
    )
