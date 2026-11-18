from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie  # the page's JS sends this cookie back as X-CSRFToken on POSTs
def home(request):
    # Serve the single-page client directly (not via the template engine).
    with open(settings.BASE_DIR / 'client' / 'index.html') as f:
        return HttpResponse(f.read())


def preview(request):
    """Render Markdown exactly as the wiki/blog will (editor preview). Staff only."""
    from config.api import json_body, staff_only
    from config.markup import render

    denied = staff_only(request)
    if denied:
        return denied
    data = json_body(request) or {}
    return JsonResponse({"html": render(data.get("body") or "")})


def me(request):
    """Who is viewing: lets the UI show/hide admin-only controls."""
    u = request.user
    return JsonResponse({
        "authenticated": u.is_authenticated,
        "is_staff": bool(u.is_authenticated and u.is_staff),
        "username": u.get_username() if u.is_authenticated else None,
        "staging": staging_info(),
    })


def staging_info():
    """None on the real Pi; on the staging copy, what data was last loaded from the Pi."""
    if not settings.GREENPI_STAGING:
        return None
    import json
    info = {"snapshot": None}
    path = settings.DATA_DIR / "staging-snapshot.json"
    try:
        info["snapshot"] = json.loads(path.read_text())
    except (OSError, ValueError):
        pass
    return info
