# Milk Basket Constants

# Whatsapp OTP request template
WA_OTP_MESSAGE = '''Dear {0}, use this One Time Password {1} to log in to your Milk Basket account. This OTP will be valid for the next 24 hours. 🔐🛅'''

WA_OTP_MESSAGE_TEMPLATE = {
    "messaging_product": "whatsapp",
    "to": {0},
    "type": "template",
    "template": {
        "name": "login_otp_v1",
        "language": {
            "code": "en",
            "policy": "deterministic"
        },
        "components": [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": {1}
                    },
                    {
                        "type": "text",
                        "text": {2}
                    },
                ]
            }
        ]
    }
}
