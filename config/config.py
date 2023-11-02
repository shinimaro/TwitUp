from dataclasses import dataclass
from environs import Env


@dataclass
class TgBot:
    token: str
    support_name: str
    support_id: int
    admin: int
    superadmin: str
    feedback_group: str


@dataclass
class DatabaseConfig:
    db_host: str
    db_user: str
    db_password: str
    db_name: str


@dataclass
class Proxy:
    proxy_host: str
    proxy_port: int


@dataclass
class BaseTwitterAccount:
    tw_login: str
    tw_password: str


@dataclass
class Webdrivers:
    num_webdrivers: int
    max_webdrivers: int


@dataclass
class Config:
    tg_bot: TgBot
    database: DatabaseConfig
    proxy: Proxy
    base_twitter_account: BaseTwitterAccount
    webdrivers: Webdrivers


def load_config(path: str | None = None) -> Config:
    env = Env()
    env.read_env(path)
    return Config(tg_bot=(TgBot(token=env('BOT_TOKEN'),
                                support_name=env('SUPPORT_NAME'),
                                support_id=env('ADMIN_IDS'),
                                admin=int(env('ADMIN_IDS')),
                                superadmin=env('SUPERADMIN_ID'),
                                feedback_group=env('FEEDBACK_GROUP'))),
                  database=(DatabaseConfig(db_host=env('HOST'),
                                           db_user=env('USER'),
                                           db_password=env('PASSWORD'),
                                           db_name=env('DB_NAME'))),
                  proxy=(Proxy(proxy_host=env('PROXY_HOST'),
                               proxy_port=int(env('PROXY_PORT')))),
                  base_twitter_account=(BaseTwitterAccount(tw_login=env('TWITTER_LOGIN'),
                                                           tw_password=env('TWITTER_PASSWORD'))),
                  webdrivers=(Webdrivers(num_webdrivers=int(env('WEBDRIVERS')),
                                         max_webdrivers=int(env('MAX_WEBDRIVERS')))))


