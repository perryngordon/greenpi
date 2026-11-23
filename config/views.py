from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie  # the page's JS sends this cookie back as X-CSRFToken on POSTs
def home(request):
    # Serve the single-page client directly (not via the template engine).
    with open(settings.BASE_DIR / 'client' / 'index.html') as f:
        return HttpResponse(f.read())


def preview(request):
    """Render Markdown exactly as the wiki/blog will (editor preview). Editors only."""
    from config.api import editor_only, json_body
    from config.markup import render

    denied = editor_only(request)
    if denied:
        return denied
    data = json_body(request) or {}
    return JsonResponse({"html": render(data.get("body") or "")})


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
