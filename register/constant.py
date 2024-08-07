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

WA_PAYMENT_MESSAGE_TEMPLATE_V2 = {
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": {0},
    "type": "template",
    "template": {
        "name": "payment_received_v2",
        "language": {
            "code": "en",
            "policy": "deterministic"
        },
        "components": [
            {
                "type": "header",
                "parameters": [
                    {
                        "type": "image",
                        "image": {
                            "link": "https://milk.cyberboy.in/static/bill/thankyou_golden_edition_v1.jpg"
                        }
                    }
                ]
            },
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

Thanks 🙏🐄🥛🧾
{3}'''

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

WA_DUE_MESSAGE_TEMPLATE_V2 = {
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": {0},
    "type": "template",
    "template": {
        "name": "bill_generated_v2",
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
                    }
                ]
            },
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [
                    {
                        "type": "text",
                        "text": {5}
                    }
                ]
            }
        ]
    }
}

WA_DUE_MESSAGE_TEMPLATE_V3 = {
    "messaging_product": "whatsapp",
    "recipient_type": "individual",
    "to": {0},
    "type": "template",
    "template": {
        "name": "bill_generated_v3",
        "language": {
            "code": "en",
            "policy": "deterministic"
        },
        "components": [
            {
                "type": "header",
                "parameters": [
                    {
                        "type": "image",
                        "image": {
                            "link": "https://milk.cyberboy.in/static/bill/due_banner_v1.png"
                        }
                    }
                ]
            },
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
                    }
                ]
            },
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [
                    {
                        "type": "text",
                        "text": {4}
                    }
                ]
            }
        ]
    }
}

# Whatsapp new message alert
WA_NEW_MESSAGE = '''📢 🆕 📩 You have a new message from {0}. 

Open Milk Basket or click the button below to view messages.👇
'''

WA_NEW_MESSAGE_TEMPLATE = {
    "messaging_product": "whatsapp",
    "to": {0},
    "type": "template",
    "template": {
        "name": "unread_message_v1",
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
                ]
            }
        ]
    }
}
