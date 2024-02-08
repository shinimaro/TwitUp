from dataclasses import dataclass

from environs import Env


@dataclass(frozen=True, slots=True)
class TgBot:
    token: str
    feedback_group: str
    main_admin: int


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    db_host: str
    db_user: str
    db_password: str
    db_name: str


@dataclass(frozen=True, slots=True)
class RedisConfig:
    redis_host: str
    redis_port: int


@dataclass(frozen=True, slots=True)
class Webdrivers:
    num_webdrivers: int
    webdrivers_at_once: int
    max_webdrivers: int


@dataclass(frozen=True, slots=True)
class Config:
    tg_bot: TgBot
    database: DatabaseConfig
    redis: RedisConfig
    webdrivers: Webdrivers


def load_config(path: str | None = None) -> Config:
    env = Env()
    env.read_env(path)
    return Config(tg_bot=(TgBot(token=env('BOT_TOKEN'),
                                feedback_group=env('FEEDBACK_GROUP'),
                                main_admin=env.int('MAIN_ADMIN'))),
                  database=(DatabaseConfig(db_host=env('DB_HOST'),
                                           db_user=env('DB_USER'),
                                           db_password=env('DB_PASSWORD'),
                                           db_name=env('DB_NAME'))),
                  redis=(RedisConfig(redis_host=env('REDIS_HOST'),
                                     redis_port=env.int('REDIS_PORT'))),
                  webdrivers=(Webdrivers(num_webdrivers=env.int('WEBDRIVERS'),
                                         webdrivers_at_once=env.int("WEBDRIVERS_AT_ONCE"),
                                         max_webdrivers=env.int('MAX_WEBDRIVERS'))))
