#!/usr/bin/env python
# -*- coding: UTF-8 -*-


import time
from datetime import datetime
from pandas import DataFrame

from ib.opt import Connection, message
from ib.ext.Contract import Contract
from ib.ext.Order import Order

from ezibpy.utils import dataTypes

# =============================================================
# set debugging mode
# levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
# filename=LOG_FILENAME
# =============================================================
import logging
# import sys
# logging.basicConfig(stream=sys.stdout, level=self.log(mode="debug", msg=
    # format='%(asctime)s [%(levelname)s]: %(message)s')


class ezIBpy():

    def log(self, mode, msg):
        if self.logging:
            if mode == "debug":
                logging.debug(msg)
            elif mode == "info":
                logging.info(msg)
            elif mode == "warning":
                logging.warning(msg)
            elif mode == "error":
                logging.error(msg)
            elif mode == "critical":
                logging.critical(msg)


    """
    https://www.interactivebrokers.com/en/software/api/apiguide/java/java_eclientsocket_methods.htm
    """
    # ---------------------------------------------------------
    def __init__(self):

        self.__version__   = 0.05

        self.logging       = False

        self.clientId      = 0
        self.port          = 7496 # 7496 = TWS, 4001 = IBGateway
        self.host          = "localhost"
        self.ibConn        = None

        self.time          = 0
        self.commission    = 0


        self.accountCode   = 0
        self.orderId       = 1

        # auto-construct for every contract/order
        self.tickerIds     = { 0: "SYMBOL" }
        self.contracts     = {}
        self.orders        = {}
        self.orderBook     = {}
        self.account       = {}
        self.positions     = {}
        self.portfolio     = {}

        # holds market data
        tickDF = DataFrame({
            "datetime":[0], "bid":[0], "bidsize":[0],
            "ask":[0], "asksize":[0], "last":[0], "lastsize":[0]
            })
        tickDF.set_index('datetime', inplace=True)
        self.marketData  = { 0: tickDF } # idx = tickerId

        # holds options data
        # optionDF = DataFrame({ "datetime":[0], "bid":[0], "ask":[0], "last":[0], "impliedVol":[0], "delta":[0], "optPrice":[0], "pvDividend":[0], "gamma":[0], "vega":[0], "theta":[0], "undPrice":[0] })
        # optionDF.set_index('datetime', inplace=True)

#         optionDF = {
#             "bid":   DataFrame({ "impliedVol":[0], "delta":[0], "optPrice":[0], "pvDividend":[0], "gamma":[0], "vega":[0], "theta":[0], "undPrice":[0] }),
#             "ask":   DataFrame({ "impliedVol":[0], "delta":[0], "optPrice":[0], "pvDividend":[0], "gamma":[0], "vega":[0], "theta":[0], "undPrice":[0] }),
#             "last":  DataFrame({ "impliedVol":[0], "delta":[0], "optPrice":[0], "pvDividend":[0], "gamma":[0], "vega":[0], "theta":[0], "undPrice":[0] }),
#             "model": DataFrame({ "impliedVol":[0], "delta":[0], "optPrice":[0], "pvDividend":[0], "gamma":[0], "vega":[0], "theta":[0], "undPrice":[0] })
#         }
#         self.optionsData  = { 0: optionDF }

        # historical data contrainer
        self.historicalData = { }  # idx = symbol


    # ---------------------------------------------------------
    def connect(self, clientId, host="localhost", port=7496):
        """ Establish connection to TWS/IBGW """
        self.clientId = 0
        self.host     = host
        self.port     = port
        self.ibConn   = Connection.create(
                            host = self.host,
                            port = self.port,
                            clientId = self.clientId
                            )

        # Assign error handling function.
        self.ibConn.register(self.handleErrorEvents, 'Error')

        # Assign server messages handling function.
        self.ibConn.registerAll(self.handleServerEvents)

        # connect
        self.log(mode="info", msg="[CONNECTING TO IB]")
        self.ibConn.connect()

        # get server time
        self.getServerTime()


    # ---------------------------------------------------------
    def disconnect(self):
        """ Disconnect from TWS/IBGW """
        if self.ibConn is not None:
            self.log(mode="info", msg="[DISCONNECT TO IB]")
            self.ibConn.disconnect()


    # ---------------------------------------------------------
    def getServerTime(self):
        """ get the current time on IB """
        self.ibConn.reqCurrentTime()

    # ---------------------------------------------------------
    # Start event handlers
    # ---------------------------------------------------------
    def handleErrorEvents(self, msg):
        """ logs error messages """
        # https://www.interactivebrokers.com/en/software/api/apiguide/tables/api_message_codes.htm
        if msg.errorCode != -1: # and msg.errorCode != 2104 and msg.errorCode != 2106:
            self.log(mode="error", msg=msg)


    # ---------------------------------------------------------
    def handleServerEvents(self, msg):
        if msg.typeName == "error":
            pass

        elif msg.typeName == dataTypes["MSG_CURRENT_TIME"]:
            if self.time < msg.time:
                self.time = msg.time

        elif msg.typeName == dataTypes["MSG_TYPE_TICK_STRING"]:
            self.handleTickString(msg)

        elif msg.typeName == dataTypes["MSG_TYPE_TICK_PRICE"]:
            self.handleTickPrice(msg)

        elif msg.typeName == dataTypes["MSG_TYPE_STICK_SIZE"]:
            self.handleTickSize(msg)

        elif msg.typeName == dataTypes["MSG_TYPE_TICK_OPTION"]:
            self.handleTickOptionComputation(msg)

        elif (msg.typeName == dataTypes["MSG_TYPE_OPEN_ORDER"] or
                msg.typeName == dataTypes["MSG_TYPE_ORDER_STATUS"]):
            self.handleOrders(msg)

        elif msg.typeName == dataTypes["MSG_TYPE_HISTORICAL_DATA"]:
            self.handleHistoricalData(msg)

        elif msg.typeName == dataTypes["MSG_TYPE_ACCOUNT_UPDATES"]:
            self.handleAccount(msg)

        elif msg.typeName == dataTypes["MSG_TYPE_PORTFOLIO_UPDATES"]:
            self.handlePortfolio(msg)

        elif msg.typeName == dataTypes["MSG_TYPE_POSITION"]:
            self.handlePosition(msg)

        elif msg.typeName == dataTypes["MSG_TYPE_MANAGED_ACCOUNTS"]:
            self.accountCode = msg.accountsList

        elif msg.typeName == dataTypes["MSG_TYPE_NEXT_ORDER_ID"]:
            self.orderId     = msg.orderId

        elif msg.typeName == dataTypes["MSG_COMMISSION_REPORT"]:
            self.commission = msg.commissionReport.m_commission

        else:
            self.log(mode="info", msg="[SERVER]: "+ str(msg))
            pass

    # ---------------------------------------------------------
    # generic callback function - can be used externally
    # ---------------------------------------------------------
    def ibCallback(self, caller, msg, **kwargs):
        pass


    # ---------------------------------------------------------
    # Start admin handlers
    # ---------------------------------------------------------
    def handleAccount(self, msg):
        """
        handle account info update
        https://www.interactivebrokers.com/en/software/api/apiguide/java/updateaccountvalue.htm
        """
        track = ["BuyingPower", "CashBalance", "DayTradesRemaining",
                 "NetLiquidation", "InitMarginReq", "MaintMarginReq",
                 "AvailableFunds", "AvailableFunds-C", "AvailableFunds-S"]

        if msg.key in track:
            # self.log(mode="info", msg="[ACCOUNT]: " + str(msg))
            self.account[msg.key] = float(msg.value)

            # fire callback
            self.ibCallback(caller="handleAccount", msg=msg)

    # ---------------------------------------------------------
    def handlePosition(self, msg):
        """ handle positions changes """

        # contract identifier
        contractString = self.contractString(msg.contract)

        if msg.pos != 0 or contractString in self.contracts.keys():
            self.log(mode="info", msg="[POSITION]: " + str(msg))
            self.positions[contractString] = {
                "symbol":        contractString,
                "position":      int(msg.pos),
                "avgCost":       float(msg.avgCost),
                "account":       msg.account
            }

        # fire callback
        self.ibCallback(caller="handlePosition", msg=msg)

    # ---------------------------------------------------------
    def handlePortfolio(self, msg):
        """ handle portfolio updates """
        self.log(mode="info", msg="[PORTFOLIO]: " + str(msg))

        # contract identifier
        contractString = self.contractString(msg.contract)

        self.portfolio[contractString] = {
            "symbol":        contractString,
            "position":      int(msg.position),
            "marketPrice":   float(msg.marketPrice),
            "marketValue":   float(msg.marketValue),
            "averageCost":   float(msg.averageCost),
            "unrealizedPNL": float(msg.unrealizedPNL),
            "realizedPNL":   float(msg.realizedPNL),
            "account":       msg.accountName
        }

        # fire callback
        self.ibCallback(caller="handlePortfolio", msg=msg)


    # ---------------------------------------------------------
    def handleOrders(self, msg):
        """ handle order open & status """
        """
        It is possible that orderStatus() may return duplicate messages.
        It is essential that you filter the message accordingly.
        """
        self.log(mode="info", msg="[ORDER]: " + str(msg))

        # get server time
        self.getServerTime()
        time.sleep(0.001)

        # we need to handle mutiple events for the same order status
        duplicateMessage = False;

        # open order
        if msg.typeName == dataTypes["MSG_TYPE_OPEN_ORDER"]:
            # contract identifier
            contractString = self.contractString(msg.contract)

            if msg.orderId in self.orders:
                duplicateMessage = True
            else:
                self.orders[msg.orderId] = {
                    "id":       msg.orderId,
                    "symbol":   contractString,
                    "contract": msg.contract,
                    "status":   "OPENED",
                    "reason":   None,
                    "avgFillPrice": 0.,
                    "parentId": 0,
                    "time": datetime.fromtimestamp(int(self.time))
                }

        # order status
        elif msg.typeName == dataTypes["MSG_TYPE_ORDER_STATUS"]:
            if self.orders[msg.orderId]['status'] == msg.status.upper():
                duplicateMessage = True
            else:
                self.orders[msg.orderId]['status']       = msg.status.upper()
                self.orders[msg.orderId]['reason']       = msg.whyHeld
                self.orders[msg.orderId]['avgFillPrice'] = float(msg.avgFillPrice)
                self.orders[msg.orderId]['parentId']     = int(msg.parentId)
                self.orders[msg.orderId]['time']         = datetime.fromtimestamp(int(self.time))

            # remove from orders?
            # if msg.status.upper() == 'CANCELLED':
            #     del self.orders[msg.orderId]

        # fire callback
        if duplicateMessage == False:
            self.ibCallback(caller="handleOrders", msg=msg)

    # ---------------------------------------------------------
    # Start price handlers
    # ---------------------------------------------------------
    def handleHistoricalData(self, msg):
        # self.log(mode="debug", msg="[HISTORY]: " + str(msg))
        print('.', end="",flush=True)

        if msg.date[:8].lower() == 'finished':
            print(self.historicalData)
            if self.csv_path != None:
                for sym in self.historicalData:
                    # print("[HISTORY FINISHED]: " + str(sym.upper()))
                    # contractString = self.contractString(str(sym))
                    contractString = str(sym)
                    print("[HISTORY FINISHED]: " + contractString)
                    self.historicalData[sym].to_csv(
                        self.csv_path + contractString +'.csv'
                        );

            print('.')
            # fire callback
            self.ibCallback(caller="handleHistoricalData", msg=msg, completed=True)

        else:
            # create tick holder for ticker
            if len(msg.date) <= 8: # daily
                ts = datetime.strptime(msg.date, dataTypes["DATE_FORMAT"])
                ts = ts.strftime(dataTypes["DATE_FORMAT_HISTORY"])
            else:
                ts = datetime.fromtimestamp(int(msg.date))
                ts = ts.strftime(dataTypes["DATE_TIME_FORMAT_LONG"])

            hist_row = DataFrame(index=['datetime'], data={
                "datetime":ts, "O":msg.open, "H":msg.high,
                "L":msg.low, "C":msg.close, "V":msg.volume,
                "OI":msg.count })
            hist_row.set_index('datetime', inplace=True)

            symbol = self.tickerSymbol(msg.reqId)
            if symbol not in self.historicalData.keys():
                self.historicalData[symbol] = hist_row
            else:
                self.historicalData[symbol] = self.historicalData[symbol].append(hist_row)

            # fire callback
            self.ibCallback(caller="handleHistoricalData", msg=msg, completed=False)

    # ---------------------------------------------------------
    def handleTickPrice(self, msg):
        """
        holds latest tick bid/ask/last price
        """
        # self.log(mode="debug", msg="[TICK PRICE]: " + dataTypes["PRICE_TICKS"][msg.field] + " - " + str(msg))
        # return
        # create tick holder for ticker
        if msg.tickerId not in self.marketData.keys():
            self.marketData[msg.tickerId] = self.marketData[0].copy()

        # bid price
        if msg.canAutoExecute == 1 and msg.field == dataTypes["FIELD_BID_PRICE"]:
            self.marketData[msg.tickerId]['bid'] = float(msg.price)
        # ask price
        elif msg.canAutoExecute == 1 and msg.field == dataTypes["FIELD_ASK_PRICE"]:
            self.marketData[msg.tickerId]['ask'] = float(msg.price)
        # last price
        elif msg.field == dataTypes["FIELD_LAST_PRICE"]:
            self.marketData[msg.tickerId]['last'] = float(msg.price)

        # fire callback
        self.ibCallback(caller="handleTickPrice", msg=msg)

        # ---------------------------------------------------------
    def handleTickSize(self, msg):
        """
        holds latest tick bid/ask/last size
        """
        # self.log(mode="debug", msg="[TICK SIZE]: " + dataTypes["SIZE_TICKS"][msg.field] + " - " + str(msg))
        # return

        # contractString = self.tickerSymbol(msg.tickerId)
        # print("**", symbol, self.contracts[self.tickerId(msg.tickerId)].m_secType)

        # create tick holder for ticker
        if msg.tickerId not in self.marketData.keys():
            self.marketData[msg.tickerId] = self.marketData[0].copy()

        # bid size
        if msg.field == dataTypes["FIELD_BID_SIZE"]:
            self.marketData[msg.tickerId]['bidsize'] = int(msg.size)
        # ask size
        elif msg.field == dataTypes["FIELD_ASK_SIZE"]:
            self.marketData[msg.tickerId]['asksize'] = int(msg.size)
        # last size
        elif msg.field == dataTypes["FIELD_LAST_SIZE"]:
            self.marketData[msg.tickerId]['lastsize'] = int(msg.size)

        # fire callback
        self.ibCallback(caller="handleTickSize", msg=msg)

    # ---------------------------------------------------------
    def handleTickString(self, msg):
        """
        holds latest tick bid/ask/last timestamp
        """
        # create tick holder for ticker
        if msg.tickerId not in self.marketData.keys():
            self.marketData[msg.tickerId] = self.marketData[0].copy()

        # update timestamp
        if msg.tickType == dataTypes["FIELD_LAST_TIMESTAMP"]:
            ts = datetime.fromtimestamp(int(msg.value)) \
                .strftime(dataTypes["DATE_TIME_FORMAT_LONG_MILLISECS"])
            self.marketData[msg.tickerId].index = [ts]
            # self.log(mode="debug", msg="[TICK TS]: " + ts)

            # fire callback
            self.ibCallback(caller="handleTickString", msg=msg)


        elif (msg.tickType == dataTypes["FIELD_RTVOLUME"]):
            # self.log(mode="info", msg="[RTVOL]: " + str(msg))

            tick = dataTypes["RTVOL_TICKS"]
            (tick['price'], tick['size'], tick['time'], tick['volume'],
                tick['vwap'], tick['single']) = msg.value.split(';')

            try:
                tick['last']       = float(tick['price'])
                tick['lastsize']   = float(tick['size'])
                tick['volume']     = float(tick['volume'])
                tick['vwap']       = float(tick['vwap'])
                tick['single']     = tick['single'] == 'true'
                tick['instrument'] = self.tickerSymbol(msg.tickerId)

                # parse time
                s, ms = divmod(int(tick['time']), 1000)
                tick['time'] = '{}.{:03d}'.format(
                    time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(s)), ms)

                # add most recent bid/ask to "tick"
                tick['bid']     = round(self.marketData[msg.tickerId]['bid'][0], 2)
                tick['bidsize'] = round(self.marketData[msg.tickerId]['bidsize'][0], 2)
                tick['ask']     = round(self.marketData[msg.tickerId]['ask'][0], 2)
                tick['asksize'] = round(self.marketData[msg.tickerId]['asksize'][0], 2)

                # self.log(mode="debug", msg=tick['time'] + ':' + self.tickerSymbol(msg.tickerId) + "-" + str(tick))

                # fire callback
                self.ibCallback(caller="handleTickString", msg=msg, tick=tick)

            except:
                pass

        else:
            # self.log(mode="info", msg="tickString" + "-" + msg)
            # fire callback
            self.ibCallback(caller="handleTickString", msg=msg)

        # print(msg)

    # ---------------------------------------------------------
    def handleTickOptionComputation(self, msg):
        """
        holds latest option data timestamp
        only option price is kept at the moment
        https://www.interactivebrokers.com/en/software/api/apiguide/java/tickoptioncomputation.htm
        """
        # create tick holder for ticker
        if msg.tickerId not in self.marketData.keys():
            self.marketData[msg.tickerId] = self.marketData[0].copy()

        # bid
        if msg.field == dataTypes["FIELD_BID_OPTION_COMPUTATION"]:
            self.marketData[msg.tickerId]['bid'] = float(msg.optPrice)
        # ask
        elif msg.field == dataTypes["FIELD_ASK_OPTION_COMPUTATION"]:
            self.marketData[msg.tickerId]['ask'] = float(msg.optPrice)
        # last
        elif msg.field == dataTypes["FIELD_LAST_OPTION_COMPUTATION"]:
            self.marketData[msg.tickerId]['last'] = float(msg.optPrice)

        # print(msg)

        # fire callback
        self.ibCallback(caller="handleTickOptionComputation", msg=msg)

    # ---------------------------------------------------------
    # tickerId/Symbols constructors
    # ---------------------------------------------------------
    def tickerId(self, symbol):
        """
        returns the tickerId for the symbol or
        sets one if it doesn't exits
        """
        for tickerId in self.tickerIds:
            if symbol == self.tickerIds[tickerId]:
                return tickerId
                break
        else:
            tickerId = len(self.tickerIds)
            self.tickerIds[tickerId] = symbol
            return tickerId

    # ---------------------------------------------------------
    def tickerSymbol(self, tickerId):
        """ returns the symbol of a tickerId """
        try:
            return self.tickerIds[tickerId]
        except:
            return ""


    # ---------------------------------------------------------
    def contractString(self, contract, seperator="_"):
        """ returns string from contract tuple """

        contractTuple = contract
        if type(contract) != tuple:
            contractTuple = (contract.m_symbol, contract.m_secType,
                contract.m_exchange, contract.m_currency, contract.m_expiry,
                contract.m_strike, contract.m_right)

        # build identifier
        try:
            if contractTuple[1] in ("OPT", "FOP"):
                # contractString = (contractTuple[0], contractTuple[1], contractTuple[6], contractTuple[4], contractTuple[5])
                if contractTuple[5]*100 - int(contractTuple[5]*100):
                    strike = contractTuple[5]
                else:
                    strike = "{0:.2f}".format(contractTuple[5])

                contractString = (contractTuple[0] + str(contractTuple[4]) + \
                    contractTuple[6], str(strike).replace(".", ""))

            elif contractTuple[1] == "FUT":
                # round expiry day to expiry month
                exp = str(contractTuple[4])[:6]
                exp = dataTypes["MONTH_CODES"][int(exp[4:6])] + str(int(exp[:4]))
                # print(contractTuple[0], exp)
                contractString = (contractTuple[0] + exp, contractTuple[1])

            elif contractTuple[1] == "CASH":
                contractString = (contractTuple[0]+contractTuple[3], contractTuple[1])

            else: # STK
                contractString = (contractTuple[0], contractTuple[1])

            # construct string
            contractString = seperator.join(
                str(v) for v in contractString).replace(seperator+"STK", "")

        except:
            contractString = contractTuple[0]

        return contractString

    # ---------------------------------------------------------
    # contract constructors
    # ---------------------------------------------------------
    def createContract(self, contractTuple, **kwargs):
        # https://www.interactivebrokers.com/en/software/api/apiguide/java/contract.htm

        contractString = self.contractString(contractTuple)
        # print(contractString)

        # get (or set if not set) the tickerId for this symbol
        # tickerId = self.tickerId(contractTuple[0])
        tickerId = self.tickerId(contractString)

        # construct contract
        newContract = Contract()

        newContract.m_symbol   = contractTuple[0]
        newContract.m_secType  = contractTuple[1]
        newContract.m_exchange = contractTuple[2]
        newContract.m_currency = contractTuple[3]
        newContract.m_expiry   = contractTuple[4]
        newContract.m_strike   = contractTuple[5]
        newContract.m_right    = contractTuple[6]

        # add contract to pull
        # self.contracts[contractTuple[0]] = newContract
        self.contracts[tickerId] = newContract

        # print(vars(newContract))
        # print('Contract Values:%s,%s,%s,%s,%s,%s,%s:' % contractTuple)
        return newContract

    # shortcuts
    # ---------------------------------------------------------
    def createStockContract(self, symbol, exchange="SMART", currency="USD"):
        contract_tuple = (symbol, "STK", exchange, currency, "", 0.0, "")
        contract = self.createContract(contract_tuple)
        return contract

    # ---------------------------------------------------------
    def createFutureContract(self, symbol, exchange="GLOBEX", currency="USD", expiry=None):
        contract_tuple = (symbol, "FUT", exchange, currency, expiry, 0.0, "")
        contract = self.createContract(contract_tuple)
        return contract

    # ---------------------------------------------------------
    def createOptionContract(self, symbol, secType="OPT", exchange="SMART", \
        currency="USD", expiry=None, strike=0.0, otype="CALL"):
        # secType = OPT (Option) / FOP (Options on Futures)
        contract_tuple = (symbol, secType, exchange, currency, expiry, float(strike), otype)
        contract = self.createContract(contract_tuple)
        return contract

    # ---------------------------------------------------------
    def createCashContract(self, symbol, exchange="SMART", currency="USD"):
        """ Used for FX, etc:
        createCashContract("EUR", currency="USD")
        """
        contract_tuple = (symbol, "CASH", exchange, currency, "", 0.0, "")
        contract = self.createContract(contract_tuple)
        return contract

    # ---------------------------------------------------------
    # order constructors
    # ---------------------------------------------------------
    def createOrder(self, quantity, price=0., stop=0., tif="DAY", \
        fillorkill=False, iceberg=False, transmit=True, **kwargs):
        # https://www.interactivebrokers.com/en/software/api/apiguide/java/order.htm
        order = Order()
        order.m_clientId      = self.clientId
        order.m_action        = dataTypes["ORDER_ACTION_BUY"] if quantity>0 else dataTypes["ORDER_ACTION_SELL"]
        order.m_totalQuantity = abs(quantity)

        if "orderType" in kwargs:
            order.m_orderType = kwargs["orderType"]
        else:
            order.m_orderType = dataTypes["ORDER_TYPE_MARKET"] if price==0 else dataTypes["ORDER_TYPE_LIMIT"]

        order.m_lmtPrice      = price # LMT  Price
        order.m_auxPrice      = stop  # STOP Price
        order.m_tif           = tif   # DAY, GTC, IOC, GTD
        order.m_allOrNone     = int(fillorkill)
        order.hidden          = iceberg
        order.m_transmit      = int(transmit)

        # The percent offset amount for relative orders.
        if "percentOffset" in kwargs:
            order.m_percentOffset = kwargs["percentOffset"]

        # The order ID of the parent order,
        # used for bracket and auto trailing stop orders.
        if "parentId" in kwargs:
            order.m_parentId = kwargs["parentId"]

        # oca group
        # used for bracket and auto trailing stop orders.
        if "ocaGroup" in kwargs:
            order.m_ocaGroup = kwargs["ocaGroup"]

        # For TRAIL order
        if "trailingPercent" in kwargs:
            order.m_trailingPercent = kwargs["trailingPercent"]

        # For TRAIL LIMIT orders only
        if "trailStopPrice" in kwargs:
            order.m_trailStopPrice = kwargs["trailStopPrice"]


        return order


    # ---------------------------------------------------------
    def createBracketOrder(self, \
        contract, quantity, entry=0., target=0., stop=0., \
        targetOrderType=None, stopOrderType=None, label=None, \
        tif="DAY", fillorkill=False, iceberg=False, **kwargs):
        """
        creates One Cancels All Bracket Order
        """
        if label == None:
            label = "bracket_"+str(int(time.time()))

        # main order
        enteyOrder = self.createOrder(quantity, price=entry, transmit=False,
            tif=tif, fillorkill=fillorkill, iceberg=iceberg)
        entryOrderId = self.placeOrder(contract, enteyOrder)

        # target
        targetOrderId = 0
        if target > 0:
            targetOrderId = entryOrderId+1
            targetOrder   = self.createOrder(-quantity,
                price     = target,
                transmit  = False if stop > 0 else True,
                orderType = dataTypes["ORDER_TYPE_LIMIT"] if targetOrderType == None else targetOrderType,
                # ocaGroup  = label,
                parentId  = entryOrderId
            )
            self.placeOrder(contract, targetOrder, targetOrderId)

        # stop
        stopOrderId = 0
        if stop > 0:
            stopOrderId  = entryOrderId+2 # if target > 0 else entryOrderId+1
            if stopOrderType == dataTypes["ORDER_TYPE_TRAIL_STOP"]:
                stopOrder  = self.createOrder(-quantity, price=0,
                    trailingPercent = stop,
                    transmit  = True,
                    orderType = dataTypes["ORDER_TYPE_TRAIL_STOP"],
                    # ocaGroup  = label,
                    parentId  = entryOrderId
                )
            else:
                stopOrder  = self.createOrder(-quantity, price=0,
                    stop      = stop,
                    transmit  = True,
                    orderType = dataTypes["ORDER_TYPE_STOP"] if stopOrderType == None else stopOrderType,
                    # ocaGroup  = label,
                    parentId  = entryOrderId
                )

            self.placeOrder(contract, stopOrder, stopOrderId)

        return {
            "label": label,
            "entryOrderId": entryOrderId,
            "targetOrderId": targetOrderId,
            "stopOrderId": stopOrderId
            }

    # ---------------------------------------------------------
    def createTrailingStopOrder(self, contract, quantity, parentId=0, trailPercent=100.):
        """ convert hard stop ordet to trailing stop order """
        if parentId not in self.orders:
            raise ValueError("Order #"+ str(parentId) +" doesn't exist or wasn't submitted")
            return


        order = self.createOrder(quantity,
            # trailStopPrice = trailPercent,
            # stop = 0.2,
            trailingPercent = trailPercent,
            orderType = dataTypes["ORDER_TYPE_TRAIL_STOP"],
            parentId  = parentId,
            transmit  = True
        )
        return self.placeOrder(contract, order, self.orderId+1)


    # ---------------------------------------------------------
    def placeOrder(self, contract, order, orderId=None):
        """ Place order on IB TWS """
        useOrderId = self.orderId if orderId == None else orderId
        self.ibConn.placeOrder(useOrderId, contract, order)
        self.requestOrderIds(1)
        return useOrderId


    # ---------------------------------------------------------
    def cancelOrder(self, orderId=None):
        """ cancel order on IB TWS """
        useOrderId = self.orderId if orderId == None else orderId
        self.ibConn.cancelOrder(useOrderId)
        self.requestOrderIds(1)
        return useOrderId

    # ---------------------------------------------------------
    # data requesters
    # ---------------------------------------------------------
    # https://github.com/blampe/IbPy/blob/master/demo/reference_python

    # ---------------------------------------------------------
    def requestOrderIds(self, numIds=1):
        """
        Request the next valid ID that can be used when placing an order.
        Triggers the nextValidId() event, and the id returned is that next valid ID.
        # https://www.interactivebrokers.com/en/software/api/apiguide/java/reqids.htm
        """
        self.ibConn.reqIds(numIds)


    # ---------------------------------------------------------
    def requestMarketData(self, contracts=None):
        """
        Register to streaming market data updates
        https://www.interactivebrokers.com/en/software/api/apiguide/java/reqmktdata.htm
        """
        if contracts == None:
            contracts = list(self.contracts.values())
        elif not isinstance(contracts, list):
            contracts = [contracts]

        for contract in contracts:
            # tickerId = self.tickerId(contract.m_symbol)
            tickerId = self.tickerId(self.contractString(contract))
            self.ibConn.reqMktData(
                tickerId, contract, dataTypes["GENERIC_TICKS_RTVOLUME"], False)

    # ---------------------------------------------------------
    def cancelMarketData(self, contracts=None):
        """
        Cancel streaming market data for contract
        https://www.interactivebrokers.com/en/software/api/apiguide/java/cancelmktdata.htm
        """
        if contracts == None:
            contracts = list(self.contracts.values())
        elif not isinstance(contracts, list):
            contracts = [contracts]

        for contract in contracts:
            # tickerId = self.tickerId(contract.m_symbol)
            tickerId = self.tickerId(self.contractString(contract))
            self.ibConn.cancelMktData(tickerId=tickerId)


    # ---------------------------------------------------------
    def requestHistoricalData(self, contracts=None, resolution="1 min",
        lookback="1 D", data="TRADES", end_datetime=None, rth=False, csv_path=None):
        """
        Download to historical data
        https://www.interactivebrokers.com/en/software/api/apiguide/java/reqhistoricaldata.htm
        """

        self.csv_path = csv_path

        if end_datetime == None:
            end_datetime = time.strftime(dataTypes["DATE_TIME_FORMAT_HISTORY"])

        if contracts == None:
            contracts = list(self.contracts.values())

        if not isinstance(contracts, list):
            contracts = [contracts]

        for contract in contracts:
            # tickerId = self.tickerId(contract.m_symbol)
            tickerId = self.tickerId(self.contractString(contract))
            self.ibConn.reqHistoricalData(
                tickerId       = tickerId,
                contract       = contract,
                endDateTime    = end_datetime,
                durationStr    = lookback,
                barSizeSetting = resolution,
                whatToShow     = data,
                useRTH         = int(rth),
                formatDate     = 2
            )

    def cancelHistoricalData(self, contracts=None):
        """ cancel historical data stream """
        if contracts == None:
            contracts = list(self.contracts.values())
        elif not isinstance(contracts, list):
            contracts = [contracts]

        for contract in contracts:
            # tickerId = self.tickerId(contract.m_symbol)
            tickerId = self.tickerId(self.contractString(contract))
            self.ibConn.cancelHistoricalData(tickerId=tickerId)

    # ---------------------------------------------------------
    def requestPositionUpdates(self, subscribe=True):
        """ Request/cancel request real-time position data for all accounts. """
        if subscribe == True:
            self.ibConn.reqPositions()
        else:
            self.ibConn.cancelPositions()


    # ---------------------------------------------------------
    def requestAccountUpdates(self, subscribe=True):
        """
        Register to account updates
        https://www.interactivebrokers.com/en/software/api/apiguide/java/reqaccountupdates.htm
        """
        self.ibConn.reqAccountUpdates(subscribe, self.accountCode)
