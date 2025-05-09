import asyncio
import logging

import betterlogging as bl
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage

from tgbot.config import Config, load_config
from tgbot.handlers import routers_list
from tgbot.middlewares.config import ConfigMiddleware
from tgbot.middlewares.api import ApiMiddleware
from tgbot.middlewares.language import LanguageMiddleware
from tgbot.services import broadcaster
from infrastructure.some_api.api import MyApi


async def on_startup(bot: Bot, admin_ids: list[int]):
    await broadcaster.broadcast(bot, admin_ids, "Бот запустился!")


async def delete_webhook(bot: Bot):
    """
    Deletes the webhook for the bot to ensure polling works correctly.
    """
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Webhook deleted before polling.")


async def on_shutdown(api_client):
    """
    Gracefully close API client when bot shuts down.
    """
    if api_client:
        await api_client.close()
        logging.info("API client closed successfully")


def register_global_middlewares(dp: Dispatcher, config: Config, api_client=None, session_pool=None):
    """
    Register global middlewares for the given dispatcher.
    Global middlewares here are the ones that are applied to all the handlers (you specify the type of update)

    :param dp: The dispatcher instance.
    :type dp: Dispatcher
    :param config: The configuration object from the loaded configuration.
    :param api_client: API client instance to be passed to handlers.
    :param session_pool: Optional session pool object for the database using SQLAlchemy.
    :return: None
    """
    middleware_types = [
        ConfigMiddleware(config),
        # DatabaseMiddleware(session_pool),
    ]
    
    if api_client:
        middleware_types.append(ApiMiddleware(api_client))
        middleware_types.append(LanguageMiddleware())

    for middleware_type in middleware_types:
        dp.message.outer_middleware(middleware_type)
        dp.callback_query.outer_middleware(middleware_type)


def setup_logging():
    """
    Set up logging configuration for the application.

    This method initializes the logging configuration for the application.
    It sets the log level to INFO and configures a basic colorized log for
    output. The log format includes the filename, line number, log level,
    timestamp, logger name, and log message.

    Returns:
        None

    Example usage:
        setup_logging()
    """
    log_level = logging.INFO
    bl.basic_colorized_config(level=log_level)

    logging.basicConfig(
        level=logging.INFO,
        format="%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting bot")


def get_storage(config):
    """
    Return storage based on the provided configuration.

    Args:
        config (Config): The configuration object.

    Returns:
        Storage: The storage object based on the configuration.

    """
    if config.tg_bot.use_redis:
        return RedisStorage.from_url(
            config.redis.dsn(),
            key_builder=DefaultKeyBuilder(with_bot_id=True, with_destiny=True),
        )
    else:
        return MemoryStorage()


async def main():
    setup_logging()

    config = load_config(".env")
    storage = get_storage(config)
    api_client = MyApi()

    async with Bot(token=config.tg_bot.token) as bot:
        dp = Dispatcher(storage=storage)
        dp.include_routers(*routers_list)
        register_global_middlewares(dp, config, api_client)
        await delete_webhook(bot)
        await on_startup(bot, config.tg_bot.admin_ids)
        await dp.start_polling(bot)
    await on_shutdown(api_client)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Бот був вимкнений!")
