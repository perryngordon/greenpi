from django.http import HttpResponse
from django.conf import settings
import os

def home(request):
    # Serve the client index.html directly as a response
    content = open(os.path.join(settings.BASE_DIR, 'client', 'index.html')).read()
    return HttpResponse(content)
