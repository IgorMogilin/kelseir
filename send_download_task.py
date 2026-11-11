"""Отладочный скрипт: отправить задачу в очередь вручную (вместо бота)."""

import asyncio

from worker.main import broker, final_download_audio


async def main() -> None:
    await broker.startup()
    await final_download_audio.kiq(
        user_id=1,
        youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        chat_id=1,
    )
    print("Задача отправлена в очередь")
    await broker.shutdown()


asyncio.run(main())
