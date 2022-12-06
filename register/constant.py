# Milk Basket Constants

# SMS message templates
PAYMENT_TEMPLATE_ID = '1507160931387192586'
SMS_PAYMENT_MESSAGE = '''Dear {0},
Payment of Rs {1} received on {2}. Transaction #{3}.
Thanks,
[Milk Basket]'''

DUE_TEMPLATE_ID = '1507160931378853480'
SMS_DUE_MESSAGE = '''Dear {0},
Total due amount for the month of {1} is Rs {2}.

[Milk Basket]'''

# Whatsapp message templates
WA_PAYMENT_MESSAGE = '''Dear {0},
Payment of ₹{1} received on {2}. 

Transaction #{3} ✅

Thank you for shopping with us. 🙏'''

WA_PAYMENT_MESSAGE_TEMPLATE = {
    "messaging_product": "whatsapp",
    "to": {0},
    "type": "template",
    "template": {
        "name": "payment_received",
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
                    {
                        "type": "text",
                        "text": {3}
                    },
                    {
                        "type": "text",
                        "text": {4}
                    }
                ]
            }
        ]
    }
}

WA_DUE_MESSAGE = '''Dear {0},
Your bill of ₹{1} for the month of {2} has been generated.

You can view the bill at 🧾👉 {3}

Thanks 🙏🐄🥛🧾'''

WA_DUE_MESSAGE_TEMPLATE = {
    "messaging_product": "whatsapp",
    "to": {0},
    "type": "template",
    "template": {
        "name": "bill_generated_v1",
        "language": {
            "code": "en",
            "policy": "deterministic"
        },
        "components": [
            {
                "type": "header",
                "parameters": [
                    {
                        "type": "text",
                        "text": {1}

                    }
                ]
            },

            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": {2}
                    },
                    {
                        "type": "text",
                        "text": {3}
                    },
                    {
                        "type": "text",
                        "text": {4}
                    },
                    {
                        "type": "text",
                        "text": {5}
                    }
                ]
            }
        ]
    }
}
