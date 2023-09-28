from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.proxy import Proxy, ProxyType

from config.config import load_config

config = load_config()


async def webdriver():
    # Установка прокси
    proxy = Proxy()
    proxy.proxyType = ProxyType.MANUAL
    proxy.http_proxy = str(config.proxy.proxy_host) + ':' + str(config.proxy.proxy_port)

    # Установка вебдрайвера и присоединение прокси
    options = ChromeOptions()
    options.add_argument('--proxy-server=http://{0}'.format(proxy.http_proxy))
    # Отключение информации о том, что это вебдрайвер
    options.add_argument('--disable-blink-features=AutomationControlled')
    # Скрытие браузера
    # options.add_argument('--headless')
    # Установка вебдрайвера и присоединение прокси
    driver = Chrome(options=options)

    return driver
