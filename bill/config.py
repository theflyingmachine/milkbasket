import json

import paytmchecksum
import requests

from milkbasket.secret import PAYTM_MID, PAYTM_WEBSITE, PAYTM_ENVIRONMENT, PAYTM_MERCHANT_KEY, \
    CALLBACK_URL


# order_id = 'order_' + str(datetime.datetime.now().timestamp())
# Allowed Payment Modes
# BALANCE, PPBL, UPI, CREDIT_CARD DEBIT_CARD NET_BANKING EMI PAYTM_DIGITAL_CREDIT
# ALLOWED_PAYMENT_MODE = ['UPI', 'CREDIT_CARD', 'DEBIT_CARD', 'NET_BANKING'],


def getTransactionToken(amount, custId, order_id):
    paytmParams = dict()

    paytmParams["body"] = {
        "requestType": "Payment",
        "mid": PAYTM_MID,
        "websiteName": PAYTM_WEBSITE,
        "orderId": order_id,
        "callbackUrl": CALLBACK_URL,
        "enablePaymentMode": ['UPI', 'CREDIT_CARD', 'DEBIT_CARD', 'NET_BANKING'],
        "txnAmount": {
            "value": amount,
            "currency": "INR",
        },
        "userInfo": {
            "custId": custId,
        },
    }

    # Generate checksum by parameters we have in body
    # Find your Merchant Key in your Paytm Dashboard at https://dashboard.paytm.com/next/apikeys 
    checksum = paytmchecksum.generateSignature(json.dumps(paytmParams["body"]), PAYTM_MERCHANT_KEY)

    paytmParams["head"] = {
        "signature": checksum
    }

    post_data = json.dumps(paytmParams)

    url = PAYTM_ENVIRONMENT + "/theia/api/v1/initiateTransaction?mid=" + PAYTM_MID + "&orderId=" + order_id

    response = requests.post(url, data=post_data,
                             headers={"Content-type": "application/json"}).json()
    response_str = json.dumps(response)
    res = json.loads(response_str)
    if res["body"]["resultInfo"]["resultStatus"] == 'S':
        token = res["body"]["txnToken"]
    else:
        token = ""
    return token


def transactionStatus(order_id):
    paytmParams = dict()
    paytmParams["body"] = {
        "mid": PAYTM_MID,
        # Enter your order id which needs to be check status for
        "orderId": order_id,
    }
    checksum = paytmchecksum \
        .generateSignature(json.dumps(paytmParams["body"]), PAYTM_MERCHANT_KEY)

    # head parameters
    paytmParams["head"] = {
        "signature": checksum
    }

    # prepare JSON string for request
    post_data = json.dumps(paytmParams)

    url = PAYTM_ENVIRONMENT + "/v3/order/status"

    response = requests.post(url, data=post_data,
                             headers={"Content-type": "application/json"}).json()
    response_str = json.dumps(response)
    res = json.loads(response_str)
    msg = "Transaction Status Response"
    return res['body']
