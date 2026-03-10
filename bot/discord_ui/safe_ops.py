from __future__ import annotations

from typing import Any

import asyncio
import discord


async def safe_edit_message(message: discord.Message, *, retry_delay: float = 0.5, max_retries: int = 2, **kwargs: Any) -> bool:
    """
    Safely edit a Discord message.
    - Swallows NotFound/Forbidden.
    - Retries a couple of times on HTTPException (incl. rate limits) with small delay.
    """
    for attempt in range(max_retries + 1):
        try:
            await message.edit(**kwargs)
            return True
        except (discord.NotFound, discord.Forbidden):
            return False
        except discord.HTTPException:
            if attempt >= max_retries:
                return False
            await asyncio.sleep(retry_delay)
        except Exception:
            return False


async def safe_delete_message(message: discord.Message, *, retry_delay: float = 0.5, max_retries: int = 1) -> bool:
    """
    Safely delete a Discord message.
    - Swallows NotFound/Forbidden.
    - Retries once on HTTPException.
    """
    for attempt in range(max_retries + 1):
        try:
            await message.delete()
            return True
        except (discord.NotFound, discord.Forbidden):
            return False
        except discord.HTTPException:
            if attempt >= max_retries:
                return False
            await asyncio.sleep(retry_delay)
        except Exception:
            return False

