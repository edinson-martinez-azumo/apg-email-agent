"""Settings endpoints for automated mode configuration."""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from app.core.deps import DB
from app.db.models.app_setting import AppSetting

router = APIRouter()

# Default values
DEFAULT_AUTO_SYNC = True
DEFAULT_AUTO_GENERATE = False
DEFAULT_AUTO_SEND = False
DEFAULT_POLL_INTERVAL_SECONDS = 60
VALID_POLL_INTERVALS = [30, 60, 120, 300, 600]


class SettingsResponse(BaseModel):
    auto_sync: bool
    auto_generate: bool
    auto_send: bool
    polling_interval_seconds: int

    model_config = {'from_attributes': True}


class SettingsUpdate(BaseModel):
    auto_sync: bool = True
    auto_generate: bool = False
    auto_send: bool = False
    polling_interval_seconds: int = Field(ge=15, le=3600)


@router.get('/settings', response_model=SettingsResponse)
async def get_settings(db: DB):
    result = await db.execute(
        select(AppSetting).where(AppSetting.key.in_([
            'auto_sync', 'auto_generate', 'auto_send', 'polling_interval_seconds',
        ]))
    )
    rows = result.scalars().all()

    settings_dict = {row.key: row.value for row in rows}

    auto_sync = settings_dict.get('auto_sync', str(DEFAULT_AUTO_SYNC)).lower() == 'true'
    auto_generate = settings_dict.get('auto_generate', str(DEFAULT_AUTO_GENERATE)).lower() == 'true'
    auto_send = settings_dict.get('auto_send', str(DEFAULT_AUTO_SEND)).lower() == 'true'
    poll_interval = int(settings_dict.get('polling_interval_seconds', str(DEFAULT_POLL_INTERVAL_SECONDS)))

    # Clamp interval to valid values
    valid_intervals = sorted([i for i in VALID_POLL_INTERVALS if i <= poll_interval])
    if valid_intervals:
        poll_interval = valid_intervals[-1]
    else:
        poll_interval = min(VALID_POLL_INTERVALS)

    return SettingsResponse(
        auto_sync=auto_sync,
        auto_generate=auto_generate,
        auto_send=auto_send,
        polling_interval_seconds=poll_interval,
    )


@router.put('/settings', response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate, db: DB):
    now = datetime.now(timezone.utc)

    keys_to_fetch = ['auto_sync', 'auto_generate', 'auto_send', 'polling_interval_seconds']
    existing_result = await db.execute(
        select(AppSetting).where(AppSetting.key.in_(keys_to_fetch))
    )
    existing_rows = {row.key: row for row in existing_result.scalars().all()}

    # Also fetch old key for migration
    old_result = await db.scalar(
        select(AppSetting).where(AppSetting.key == 'automated_mode')
    )
    if old_result:
        old_value = old_result.value.lower() == 'true'
        old_result.value = 'true' if (payload.auto_sync and payload.auto_generate and payload.auto_send) else 'false'
        old_result.updated_at = now

    for key in keys_to_fetch:
        if key in existing_rows:
            existing_rows[key].value = str(getattr(payload, key)).lower()
            existing_rows[key].updated_at = now
        else:
            db.add(AppSetting(
                key=key,
                value=str(getattr(payload, key)).lower(),
                updated_at=now,
            ))

    await db.commit()

    return SettingsResponse(
        auto_sync=payload.auto_sync,
        auto_generate=payload.auto_generate,
        auto_send=payload.auto_send,
        polling_interval_seconds=payload.polling_interval_seconds,
    )
