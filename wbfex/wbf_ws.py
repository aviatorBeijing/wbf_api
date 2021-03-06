#! /usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import time
import json
from websocket import create_connection
import datetime
import gzip
import copy

WS_URL = "wss://ws.wbf.live/kline-api/ws"
"""
# another possible url
WS_URL = "wss://ws.wbf.info/kline-api/ws"
"""

class WBFExWebsocket(threading.Thread):
    def __init__(self, on_update_trade, on_update_depth, **kwags):
        self.last_update = time.time()

        self.on_update_trade = on_update_trade
        self.on_update_depth = on_update_depth
        if 'ws_symbol' in kwags:
            ws_symbol = copy.deepcopy(kwags['ws_symbol'])
        else:
            ws_symbol = []
        if not isinstance(ws_symbol, list):
            ws_symbol = [ws_symbol]
        symbol_dic = {}
        for i in range(len(ws_symbol)):
            n_symbol = ws_symbol[i].lower().replace('/', '')
            symbol_dic[n_symbol] = ws_symbol[i]
            ws_symbol[i] = n_symbol
        self.symbol_dic = symbol_dic
        self.ws_symbol = ws_symbol

        threading.Thread.__init__(self)
        self.ws = None
    def check_conncet(self):
        if self.ws.sock and self.ws.sock.connected:
            return True
        else:
            return False
    def _connect(self):
        for i in range(50):
            try:
                ws = create_connection(WS_URL)
            except Exception as e:
                print('connect error',e)
                pass
            else:
                self.ws = ws
                self.last_keep_alive = time.time()
                self.last_update = time.time()
                return 0
        return 1
    def send_message(self, message):
        if not self.ws:
            print('ws is none')
            r = self._connect()
        else:
            try:
                self.ws.send(message)
            except Exception as e:
                print('发送消息失败，消息为：' + message,e)
    def _keep_alive_receive(self, message):
        if 'ping' in message:
            pong_dic = json.dumps({'pong': str(message['ping'])})
            self.send_message(pong_dic)
            self.last_keep_alive = time.time()
            return 0
        else:
            return 1
    def _receive(self):
        raw_message = self.ws.recv()

        raw_message = gzip.decompress(raw_message).decode('utf-8')
        _receive_timestamp = time.time()
        try:
            message = json.loads(raw_message)
        except Exception as e:
            print('接收数据错误，数据为：', raw_message)
        else:
            r = self._keep_alive_receive(message)
            if not r:
                return 0
            else:
                if 'tick' in message and message['tick'] is not None:
                    channel = message['channel']
                    self.last_update = time.time()
                    message = message
                    if channel.split('_')[-2] == 'depth':
                        symbol = self.symbol_dic[channel.split('_')[1]]
                        _update_data = {}
                        _update_data['channel'] = channel
                        _update_data['timestamp'] = message['ts']
                        _update_data['rec_timestamp'] =_receive_timestamp * 1000
                        _update_data['symbol'] = symbol
                        _update_data['exchange'] = 'wbf'
                        _update_data['symbol_name'] = symbol
                        _update_data['asks'] = message['tick']['asks']
                        _update_data['bids'] = message['tick']['buys']
                        _update_data['bids'].sort()
                        _update_data['bids'].reverse()
                        _update_data['asks'].sort()
                        _update_data['datetime'] = datetime.datetime.utcfromtimestamp(message['ts'] / 1000).isoformat()
                        _update_data['data_type'] = 'depth'
                        self.on_update_depth(channel, _update_data)
                    if channel.split('_')[-2] == 'trade':
                        _update_data = []
                        symbol = self.symbol_dic[channel.split('_')[1]]
                        for key in message['tick']['data']:
                            _trade_data = {}
                            _trade_data['symbol'] = symbol
                            _trade_data['timestamp'] = key['ts']
                            _trade_data['datetime'] = datetime.datetime.utcfromtimestamp(key['ts'] / 1000).isoformat()
                            _trade_data['rec_timestamp'] = _receive_timestamp * 1000
                            _trade_data['info'] = key
                            _trade_data['price'] = key['price']
                            _trade_data['amount'] = key['vol']
                            _trade_data['side'] = key['side'].lower()
                            _trade_data['data_type'] = 'trade'
                            _trade_data['exchange'] = 'wbf'
                            _update_data.append(_trade_data)
                        self.on_update_trade(channel, _update_data)


    def _subscribe(self):
        for symbol in self.ws_symbol:
            symbol_i = symbol.replace('/','').lower()
            #rdata = json.dumps({"event": "sub","params":{"channel":"market_"+symbol_i+"_depth_step0","top":150}})
            #print(rdata)
            self.send_message(json.dumps({"event": "sub","params":{"channel":"market_"+symbol_i+"_depth_step0","top":150}}))
            self.send_message(json.dumps({"event": "sub","params":{"channel":"market_"+symbol_i+"_trade_ticker"}}))

    def run(self):
        t = 1
        try:
            self._connect()
        except Exception as e:
            print('初始化连接失败',e)
            t = 0
        try:
            self._subscribe()
        except Exception as e:
            print('订阅失败！',e)
            t = 0

        while t:
            try:
                self._receive()
            except Exception as e:
                print('处理收到的消息失败',e)
                break

"""""""""""""""""""""""""""""""""
Trade|Depth Data Handler
"""""""""""""""""""""""""""""""""
def handle_simple(channel, data):
    if 'depth' in channel:
        print( data['symbol'], 'bid1:{}, ask1:{}'.format(data['bids'][0], data['asks'][0]) )
    elif 'trade' in channel:
        for d in data:
            di = d['info']
            print( '[trade]', datetime.datetime.fromtimestamp( float(d['timestamp'])/1000), di['side'], d['symbol'], di['price'], di['vol'], di['amount'])

"""""""""""""""""""""""""""""""""
Trail run
"""""""""""""""""""""""""""""""""
if __name__ == '__main__':
    wbf_ws = WBFExWebsocket(on_update_trade=handle_simple, on_update_depth=handle_simple, ws_symbol=['BTC/USDT','ETH/USDT'])
    wbf_ws.start()