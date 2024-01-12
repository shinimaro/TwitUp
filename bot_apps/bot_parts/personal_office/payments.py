import datetime
from decimal import Decimal as dec

import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware

bsc = "https://bsc-dataseed.binance.org/"
web3 = Web3(Web3.HTTPProvider(bsc))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)


class CryptoPay:
    def __init__(self):
        self.main_url = "http://213.183.48.235:23151/api"

        # make session and set headers
        api_key = "dea9de52-36eb-44a0-8a22-87650d4d6862"
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
        }
        self.session = requests.Session()
        self.session.headers.update(headers)

    def Transactions(self, last_id: str):
        next_id = dec(last_id) + dec('10')
        we_continue = True
        ready_answer = []
        while we_continue:
            ids = [x for x in range(int(last_id), int(str(next_id)))]

            data = {"ids": ids}
            response = self.session.post(self.main_url + "/transactions",
                                         json=data)
            answer = [data for data in response.json()]

            for data in answer:
                if data['value'] == '0': continue
                transaction_time = datetime.datetime.fromtimestamp(data['timestamp'])
                data['time'] = transaction_time
                data['usd'] = dec(str(data['usd'])) / dec('100')
                ready_answer.append(data)

            if len(ids) == len(answer):
                last_id = str(next_id)
                next_id = dec(last_id) + dec('2')
            else:
                we_continue = False
        return last_id, ready_answer

    def Rates(self):
        response = self.session.post(self.main_url + "/rates")
        return response.json()

    def GetWallet(self, wallet_id: int):
        data = {"walletId": wallet_id}
        response = self.session.post(self.main_url + "/wallet",
                                     json=data)
        return response.text
