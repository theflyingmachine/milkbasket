from datetime import datetime

from django.shortcuts import redirect
from django.urls import reverse


class SessionExpiryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            timestamp_format = '%Y-%m-%dT%H:%M:%S.%fZ'
            last_visit = request.session.get('last_visit', None)
            now = datetime.now()
            if last_visit:
                last_visit = datetime.strptime(last_visit, timestamp_format)
                days_since_last_visit = (now - last_visit).days
                if days_since_last_visit > 45:
                    # If it's been more than 45 days since the last visit, log the user out
                    request.session.flush()
                    return redirect(reverse('view_register'))
            else:
                # Set the last visit time if it's not already set
                request.session['last_visit'] = now.strftime(timestamp_format)

        response = self.get_response(request)
        return response
