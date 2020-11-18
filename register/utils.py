from register.models import Customer, Register, Milk, Expense, Payment, Balance, Income


# ======== UTILITY ============
# Only helper function beyond this point
def get_active_month(customer_id, only_paid=False, all_active=True):
    """ Returns active month list of customer """
    active_months = None
    if customer_id:
        if all_active:
            active_months = Register.objects.filter(customer_id=customer_id).dates(
                'log_date', 'month', order='DESC')
        else:
            active_months = Register.objects.filter(customer_id=customer_id, paid=only_paid).dates(
                'log_date', 'month', order='DESC')

    return active_months


def get_register_month_entry(customer_id, month=False, year=False):
    """ Returns register entry of a given month """
    register_entry = None
    if customer_id:
        if month and year:
            register_entry = Register.objects.filter(customer_id=customer_id,
                                                     log_date__month=month, log_date__year=year)
        else:
            register_entry = Register.objects.filter(customer_id=customer_id)

    return register_entry


def get_register_day_entry(customer_id, day=False, month=False, year=False):
    """  Returns register entry of a given day """
    register_entry = None
    if customer_id:
        if day and month and year:
            register_entry = Register.objects.filter(customer_id=customer_id, log_date__day=day,
                                                     log_date__month=month, log_date__year=year)
        else:
            register_entry = Register.objects.filter(customer_id=customer_id)
        for entry in register_entry:
            entry.morning = True if entry.schedule == 'morning-yes' or entry.schedule == 'morning-no' else False
            entry.evening = True if entry.schedule == 'evening-yes' or entry.schedule == 'evening-no' else False
            entry.absent = True if entry.schedule == 'evening-no' or entry.schedule == 'morniing-no' else False
            entry.quantity = '' if entry.absent else f'{int(entry.quantity)} ML'

    return register_entry


def get_bill_summary(customer_id, month=False, year=False):
    bill_summary = None
    if customer_id:
        # check if customer has due
        if month and year:
            due = Register.objects.filter(customer_id=customer_id, paid=0,
                                          schedule__endswith='-yes', log_date__month=month,
                                          log_date__year=year).values_list('quantity',
                                                                           'current_price')
        else:
            due = Register.objects.filter(customer_id=customer_id, paid=0,
                                          schedule__endswith='-yes').values_list('quantity',
                                                                                 'current_price')

        if due:
            summary_sheet = [{'quantity': entry[0],
                              'unit_price': float(entry[1]),
                              'cost_price': (float(entry[0]) * float(entry[1])) / 1000
                              } for entry in due]
            unique_quantity = sorted(set([quantity['quantity'] for quantity in summary_sheet]))
            bill_summary = [{'quantity': quantity,
                             'desc': sum(
                                 1 for entry in summary_sheet if
                                 entry.get('quantity') == quantity),
                             'amount': sum(entry.get('cost_price') for entry in summary_sheet if
                                           entry.get('quantity') == quantity),
                             } for quantity in unique_quantity]
            total = {'total': sum(entry.get('amount') for entry in bill_summary)}
            bill_summary.append(total)

    return bill_summary
