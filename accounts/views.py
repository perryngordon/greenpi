"""
People and logins (JSON API used by the SPA).

Anyone may read the site. Accounts are only ever created by an admin (no
sign-up), with a one-time temporary password the person must replace on
first login. Roles: admin = User.is_staff (network, sensors, people);
gardener = any other active account (journal, wiki, almanac, photos).
"""
import re
import secrets

from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import JsonResponse

from config.api import bad_request, can_edit, is_staff, json_body, staff_only

from .avatars import AVATAR_SLUGS, AVATARS, avatar_url
from .models import profile_for

User = get_user_model()

# Brute-force guard (shared by all gunicorn workers via the file cache).
FAIL_WINDOW = 15 * 60
MAX_FAILS_PER_USER = 5
MAX_FAILS_PER_IP = 20
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,29}$")
WORDS = ("sunny", "leafy", "mossy", "frosty", "breezy", "rainy", "golden", "minty", "rosy", "sprouty",
         "tomato", "carrot", "radish", "basil", "clover", "acorn", "pepper", "maple", "fern", "tulip",
         "pumpkin", "turnip", "thyme", "willow", "pinecone", "daisy", "kale", "melon", "orchid", "squash")


def person(user):
    p = profile_for(user)
    return {
        "id": user.id, "username": user.get_username(),
        "display_name": p.display_name or user.get_username(),
        "avatar": p.avatar, "avatar_url": avatar_url(p.avatar),
        "role": "admin" if user.is_staff else "gardener",
        "active": user.is_active,
        "must_change_password": p.must_change_password,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def author_info(user):
    """Small {name, avatar_url} for showing who wrote something (None if unknown)."""
    if user is None:
        return None
    p = profile_for(user)
    return {"name": p.display_name or user.get_username(), "avatar_url": avatar_url(p.avatar)}


def temp_password():
    return f"{secrets.choice(WORDS)}-{secrets.choice(WORDS)}-{secrets.randbelow(90) + 10}"


def me_payload(request):
    from config.views import staging_info
    u = request.user
    out = {
        "authenticated": u.is_authenticated,
        "is_staff": is_staff(request),
        "can_edit": can_edit(request),
        "username": u.get_username() if u.is_authenticated else None,
        "user": person(u) if u.is_authenticated else None,
        "staging": staging_info(),
    }
    if u.is_authenticated:
        out["avatars"] = [{"slug": s, "name": n, "url": avatar_url(s)} for s, n in AVATARS]
    return out


def _fails(key):
    try:
        return cache.get(key, 0)
    except OSError:  # data drive missing: don't let the guard break logins
        return 0


def _add_fail(key):
    try:
        cache.set(key, cache.get(key, 0) + 1, FAIL_WINDOW)
    except OSError:
        pass


def _client_ip(request):
    return request.META.get("REMOTE_ADDR", "?")


def me(request):
    """GET: who is viewing. PUT {display_name, avatar}: update your own profile."""
    if request.method == "GET":
        return JsonResponse(me_payload(request))
    if not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Log in first."}, status=403)
    if request.method != "PUT":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    data = json_body(request)
    if data is None:
        return bad_request("Invalid JSON.")
    p = profile_for(request.user)
    if "display_name" in data:
        name = (data.get("display_name") or "").strip()
        if not 1 <= len(name) <= 60:
            return bad_request("Your name must be 1 to 60 characters.")
        p.display_name = name
    if "avatar" in data:
        if data["avatar"] not in AVATAR_SLUGS:
            return bad_request("Unknown avatar.")
        p.avatar = data["avatar"]
    p.save()
    return JsonResponse(me_payload(request))


def change_password(request):
    """POST {current, new}: replace your password (required after a temporary one)."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Log in first."}, status=403)
    data = json_body(request) or {}
    user = request.user
    if not user.check_password(data.get("current") or ""):
        return bad_request("Your current password isn't right.")
    new = data.get("new") or ""
    try:
        validate_password(new, user)
    except ValidationError as e:
        return bad_request(" ".join(e.messages))
    user.set_password(new)
    user.save()
    update_session_auth_hash(request, user)  # stay logged in on this device
    p = profile_for(user)
    p.must_change_password = False
    p.save()
    return JsonResponse(me_payload(request))


def login_view(request):
    """POST {username, password}: start a session."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    data = json_body(request) or {}
    username = (data.get("username") or "").strip().lower()
    ukey, ikey = f"login-fail-u:{username}", f"login-fail-ip:{_client_ip(request)}"
    if _fails(ukey) >= MAX_FAILS_PER_USER or _fails(ikey) >= MAX_FAILS_PER_IP:
        return JsonResponse({"status": "error",
                             "message": "Too many wrong passwords. Wait 15 minutes and try again."}, status=429)
    user = authenticate(request, username=username, password=data.get("password") or "")
    if user is None:
        _add_fail(ukey)
        _add_fail(ikey)
        return JsonResponse({"status": "error", "message": "Wrong name or password."}, status=400)
    try:
        cache.delete(ukey)
    except OSError:
        pass
    login(request, user)
    return JsonResponse(me_payload(request))


def logout_view(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    logout(request)
    return JsonResponse(me_payload(request))


def people(request):
    """Admin only. GET: everyone. POST {username, display_name, role}: add a person."""
    denied = staff_only(request)
    if denied:
        return denied
    if request.method == "GET":
        users = sorted(User.objects.all(), key=lambda u: (not u.is_active, person(u)["display_name"].lower()))
        return JsonResponse({"people": [person(u) for u in users]})
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    data = json_body(request) or {}
    username = (data.get("username") or "").strip().lower()
    if not USERNAME_RE.match(username):
        return bad_request("Login names are 2 to 30 lowercase letters, digits, dots, dashes or underscores.")
    if User.objects.filter(username=username).exists():
        return bad_request("That login name is taken.")
    pw = temp_password()
    user = User.objects.create_user(username=username, password=pw)
    user.is_staff = data.get("role") == "admin"
    user.save()
    p = profile_for(user)
    p.display_name = (data.get("display_name") or "").strip()[:60] or username
    p.avatar = secrets.choice(AVATAR_SLUGS)
    p.must_change_password = True
    p.save()
    return JsonResponse({"person": person(user), "temporary_password": pw})


def person_detail(request, user_id):
    """Admin only. PUT {display_name?, role?, active?, reset_password?}."""
    denied = staff_only(request)
    if denied:
        return denied
    if request.method != "PUT":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return JsonResponse({"status": "error", "message": "No such person."}, status=404)
    data = json_body(request) or {}
    is_self = user.pk == request.user.pk
    p = profile_for(user)
    out = {}
    if "display_name" in data:
        name = (data.get("display_name") or "").strip()
        if not 1 <= len(name) <= 60:
            return bad_request("Names must be 1 to 60 characters.")
        p.display_name = name
    if "role" in data or "active" in data:
        make_admin = data.get("role", "admin" if user.is_staff else "gardener") == "admin"
        active = bool(data.get("active", user.is_active))
        if is_self and (not make_admin or not active):
            return bad_request("You can't remove your own admin access.")
        user.is_staff, user.is_active = make_admin, active
    if data.get("reset_password"):
        if is_self:
            return bad_request("Change your own password from your profile instead.")
        pw = temp_password()
        user.set_password(pw)
        p.must_change_password = True
        out["temporary_password"] = pw
    user.save()
    p.save()
    return JsonResponse({"person": person(user), **out})
