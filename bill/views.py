import logging
from calendar import monthrange

from django.http import JsonResponse
from django.shortcuts import render

from register.models import Register
from register.models import Tenant
from register.utils import get_milk_current_price
from register.utils import get_mongo_client
from register.utils import get_register_day_entry

logger = logging.getLogger()


def index(request, bill_number=None):
    """Render customer view of bill"""
    if bill_number:
        logger.info('Bill View: {0}'.format(bill_number))
        template = 'bill/bill_template_simple.html'
        # template = 'bill/bill_template.html'
        context = {
            'page_title': 'Milk Basket - Bill',
        }
        logged_in = False if request.user.id else True
        bill_metadata = fetch_bill(bill_number, full_data=True, update_count=logged_in)
        if bill_metadata:
            # Fetch Tenant ID
            tenant = Register.objects.get(id=bill_metadata['transaction_ids'][0])
            tenant_id = tenant.tenant_id
            tenant_pref = Tenant.objects.filter(tenant_id=tenant_id).first()
            if tenant_pref.customers_bill_access:
                context.update(bill_metadata)
                due_transactions = Register.objects.filter(id__in=bill_metadata['transaction_ids'])
                payment_status = False if due_transactions.filter(paid=0) else True
                context.update({'payment_status': payment_status})

                # Extract months which has due for calendar
                active_months = due_transactions.dates('log_date', 'month', order='DESC')
                calendar = [{'month': active_month.strftime('%B'),
                             'year': active_month.strftime('%Y'),
                             'week_start_day': [x for x in range(0, active_month.weekday())],
                             'days_in_month': [{'day': day,
                                                'data': get_register_day_entry(
                                                    bill_metadata['customer_id'], day=day,
                                                    month=active_month.month,
                                                    year=active_month.year,
                                                    transaction_list=due_transactions)
                                                } for day in range(1, (
                                 monthrange(active_month.year, active_month.month)[1]) + 1)]
                             } for active_month in active_months]
                amount_payable = 0
                for entry in due_transactions:
                    entry.billed_amount = float(entry.current_price / 1000) * entry.quantity
                    amount_payable += float(
                        entry.current_price / 1000) * entry.quantity if not entry.paid else 0
                    entry.display_paid = 'Paid' if entry.paid else 'Due'
                    entry.display_schedule = 'Morning' if entry.schedule == 'morning-yes' else 'Evening'
                    entry.display_log_date = entry.log_date.strftime('%d-%b-%y')
                context.update({'calendar': calendar,
                                'bill_number': bill_number,
                                'bill_access': True,
                                'due_transactions': due_transactions,
                                'milk_price': get_milk_current_price(tenant_id, description=True)})

                #     Add Details for Online Payment
                # adv = get_customer_balance_amount(bill_metadata['customer_id'])
                # amount_payable = amount_payable - adv
                # if amount_payable > 0:
                #     token = config.getTransactionToken(amount_payable,
                #                                        bill_metadata['customer_id'], bill_number)
                #     if token:
                #         start_payment, _ = OnlinePayment.objects.update_or_create(
                #             customer_id=bill_metadata['customer_id'],
                #             bill_number=bill_number,
                #             order_id=bill_number,
                #             amount=amount_payable,
                #             status='Init',
                #             defaults={'token': token}
                #         )
                #     else:
                #         start_payment = OnlinePayment.objects.filter(
                #             customer_id=bill_metadata['customer_id'],
                #             bill_number=bill_number,
                #             order_id=bill_number,
                #             amount=amount_payable,
                #             status='Init').first()
                #     # print(token)
                #     context.update({
                #         'tenant': tenant_pref,
                #         'mid': config.PAYTM_MID, 'amount': amount_payable,
                #         'orderid': bill_number,
                #         'env': config.PAYTM_ENVIRONMENT,
                #         'token': start_payment.token if start_payment else None,
                #         'billNumber': bill_number,
                #     })
            else:
                context.update({'bill_access': False,
                                'customer_name': 'Not Available'})
        return render(request, template, context)
    else:
        template = 'bill/index.html'
        context = {
            'page_title': 'Milk Basket - Search Bill',
        }
        return render(request, template, context)


def validate_bill(request, full_data=False):
    """ Check if the bill is valid on search bill page"""
    response = {
        'status': 'failed',
    }
    bill_number = request.POST.get("bill-number", None)
    if request.method == "POST" and bill_number:
        bill_metadata = fetch_bill(bill_number)
        if bill_metadata:
            response.update({'metadata': str(bill_metadata['_id']), 'bill_number': bill_number})
            response['status'] = 'success' if bool(dict(bill_metadata)) else 'failed'
    return JsonResponse(response)


def fetch_bill(bill_number, full_data=False, update_count=False):
    """ Fetch bill metadata from cloud Mongo DB """
    # Fetch Bill Metadata
    metadata = get_mongo_client()
    if full_data:
        bill_metadata = metadata.find_one({'bill_number': bill_number})
    else:
        bill_metadata = metadata.find_one({'bill_number': bill_number}, {'_id': 1})
    if update_count and bill_metadata:
        tenant = Register.objects.get(id=bill_metadata['transaction_ids'][0])
        if tenant:
            tenant_pref = Tenant.objects.filter(tenant_id=tenant.tenant_id).first()
            if tenant_pref.customers_bill_access:
                metadata.update({'bill_number': bill_metadata['bill_number']},
                                {'$inc': {'views': 1, }})

    return bill_metadata

#
# @csrf_exempt
# def payment_callback(request):
#     data = dict()
#     data = request.POST
#     data = data.copy().dict()
#     if data:
#         checksum = data['CHECKSUMHASH']
#         data.pop('CHECKSUMHASH', None)
#
#         # verify checksum
#         verifySignature = paytmchecksum.verifySignature(data, config.PAYTM_MERCHANT_KEY, checksum)
#         text_error = ''
#         text_success = ''
#
#         if verifySignature:
#             text_success = "Checksum is verified.Transaction details are below"
#             # Update BE with payment status
#             OnlinePayment.objects.filter(order_id=data['ORDERID']).update(status=data['STATUS'],
#                                                                           status_msg=data[
#                                                                               'RESPMSG'],
#                                                                           online_transaction_id=
#                                                                           data.get('TXNID'),
#                                                                           raw_resp=data)
#             verify_transaction = transactionStatus(data['ORDERID'])
#             if verify_transaction['resultInfo']['resultStatus'] == 'TXN_SUCCESS':
#                 payment = OnlinePayment.objects.filter(order_id=data['ORDERID']).first()
#                 milkbasket_payment = PaymentModel.objects.filter(payment_mode='ONLINE',
#                                                                  transaction_id=payment.online_transaction_id).first()
#                 if payment.status == 'TXN_SUCCESS' and not milkbasket_payment:
#                     accept_payment(payment.customer_id, payment.amount,
#                                    payment.online_transaction_id)
#
#         else:
#             text_error = "Checksum is not verified."
#     else:
#         text_error = "Empty POST Response."
#
#     template = 'bill/callback.html'
#     context = {
#         'data': data, 'text_success': text_success, 'text_error': text_error,
#         'verifySignature': verifySignature,
#         'billNumber': payment.bill_number
#     }
#     return render(request, template, context, status=200)
#
#
# def check_txn_status(request, transaction_id=None):
#     template = 'bill/txn_status.html'
#     if transaction_id:
#         online_trans = OnlinePayment.objects.filter(online_transaction_id=transaction_id).latest(
#             'order_id')
#         verify_transaction = transactionStatus(online_trans.order_id)
#         context = {
#             'result': verify_transaction,
#             'metadata': online_trans
#         }
#         return render(request, template, context, status=200)
#
#
# def accept_payment(customer_id, payment_amount, transaction_id, sms_notification=True):
#     # Update Payment Table
#     customer = Customer.objects.filter(id=customer_id).first()
#     sms_notification = sms_notification
#     if customer_id and payment_amount:
#         payment_amount = float(payment_amount)
#         new_payment = PaymentModel(tenant_id=customer.tenant_id, customer_id=customer.id,
#                                    amount=payment_amount, payment_mode='ONLINE',
#                                    transaction_id=transaction_id)
#         try:
#             new_payment.save()
#         except:
#             pass
#             # return redirect(formatted_url)
#         balance_amount, _ = Balance.objects.get_or_create(tenant_id=customer.tenant_id,
#                                                           customer_id=customer.id)
#         adjust_amount = float(getattr(balance_amount, 'balance_amount')) if balance_amount else 0
#         # Set advance to old bal
#         balance_amount.balance_amount = 0
#         balance_amount.last_balance_amount = adjust_amount
#         balance_amount.save()
#         # Get total amount in hand
#         payment_amount = payment_amount + abs(adjust_amount)
#         # Update Register
#         accepting_payment = Register.objects.filter(tenant_id=customer.tenant_id,
#                                                     customer_id=customer_id,
#                                                     schedule__endswith='yes',
#                                                     paid=0).order_by('log_date')
#         for entry in accepting_payment:
#             if payment_amount > 0:
#                 entry_cost = float(
#                     entry.current_price / 1000 * decimal.Decimal(float(entry.quantity)))
#                 if payment_amount - entry_cost >= 0:
#                     Register.objects.filter(tenant_id=customer.tenant_id, id=entry.id).update(
#                         paid=True, transaction_number=new_payment)
#                     payment_amount = payment_amount - entry_cost
#                 elif payment_amount != 0:
#                     Balance.objects.update_or_create(tenant_id=customer.tenant_id,
#                                                      customer_id=customer_id,
#                                                      defaults={"balance_amount": payment_amount}
#                                                      )
#                     payment_amount = 0
#
#         if payment_amount != 0:
#             Balance.objects.update_or_create(tenant_id=customer.tenant_id,
#                                              customer_id=customer_id,
#                                              defaults={"balance_amount": -payment_amount}
#                                              )
#         # Send SMS notification
#         if sms_notification:
#             transaction_time = datetime.now().strftime('%d-%m-%Y %I:%M:%p')
#             sms_text = SMS_PAYMENT_MESSAGE.format(customer.name, new_payment.amount, transaction_time, new_payment.id)
#             send_sms_api(customer.contact, sms_text, PAYMENT_TEMPLATE_ID)
#
#     return True
