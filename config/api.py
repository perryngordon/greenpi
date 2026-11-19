"""Small helpers shared by the JSON API views.

Permissions: reading is public. Writing content (journal, wiki, almanac,
photos) needs any active account that has set its own password (can_edit).
Network, sensors and people need an admin (is_staff).
"""
import json

from django.http import JsonResponse


def can_edit(request):
    u = request.user
    if not (u.is_authenticated and u.is_active):
        return False
    from accounts.models import profile_for
    return not profile_for(u).must_change_password


def is_staff(request):
    return can_edit(request) and request.user.is_staff


def editor_only(request):
    """Return a 403 response unless the viewer may edit content, else None."""
    if not can_edit(request):
        return JsonResponse({"status": "error", "message": "Log in to edit."}, status=403)
    return None


def staff_only(request):
    """Return a 403 response for non-admins, else None."""
    if not is_staff(request):
        return JsonResponse({"status": "error", "message": "Only admins can do that."}, status=403)
    return None


def json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return None


def bad_request(message):
    return JsonResponse({"status": "error", "message": message}, status=400)
