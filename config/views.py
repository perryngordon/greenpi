from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie  # the page's JS sends this cookie back as X-CSRFToken on POSTs
def home(request):
    # Serve the single-page client directly (not via the template engine).
    with open(settings.BASE_DIR / 'client' / 'index.html') as f:
        return HttpResponse(f.read())


def me(request):
    """Who is viewing: lets the UI show/hide admin-only controls."""
    u = request.user
    return JsonResponse({
        "authenticated": u.is_authenticated,
        "is_staff": bool(u.is_authenticated and u.is_staff),
        "username": u.get_username() if u.is_authenticated else None,
    })
