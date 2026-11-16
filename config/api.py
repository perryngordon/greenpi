"""Small helpers shared by the JSON API views."""
import json

from django.http import JsonResponse


def is_staff(request):
    return request.user.is_authenticated and request.user.is_staff


def staff_only(request):
    """Return a 403 response for non-staff users, else None."""
    if not is_staff(request):
        return JsonResponse({"status": "error", "message": "Log in at /admin/ to edit."}, status=403)
    return None


def json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return None


def bad_request(message):
    return JsonResponse({"status": "error", "message": message}, status=400)
