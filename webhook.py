import logging
import os

from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot import bot, dp

logging.basicConfig(level=logging.INFO)

WEBHOOK_PATH = "/telegram-webhook"
PORT = int(os.getenv("PORT", "10000"))
BASE_URL = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("WEBHOOK_BASE_URL")

if not BASE_URL:
    raise RuntimeError(
        "Render URL was not found. Set WEBHOOK_BASE_URL to your public Render URL."
    )

async def on_startup(app: web.Application) -> None:
    webhook_url = f"{BASE_URL.rstrip('/')}{WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url)
    logging.info("Telegram webhook configured: %s", webhook_url)

async def on_shutdown(app: web.Application) -> None:
    # setup_application closes the bot session during application shutdown.
    logging.info("Webhook server is shutting down.")

def create_app() -> web.Application:
    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

if __name__ == "__main__":
    application = create_app()
    web.run_app(application, host="0.0.0.0", port=PORT)
