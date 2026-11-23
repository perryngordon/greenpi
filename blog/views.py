import re
import uuid
from datetime import date, datetime

from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone

from config.api import bad_request, can_edit, editor_only, json_body
from config.markup import excerpt, render

from .models import Photo, Post

PAGE_SIZE = 10
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_PHOTO_EDGE = 2000
FIRST_IMG = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")


def _visible_posts(request):
    posts = Post.objects.all()
    return posts if can_edit(request) else posts.filter(published=True)


def post_summary(p):
    m = FIRST_IMG.search(p.body or "")
    from accounts.views import author_info
    return {"id": p.id, "title": p.title, "date": p.date.isoformat(), "published": p.published,
            "excerpt": excerpt(p.body), "cover": m.group(1) if m else None,
            "author": author_info(p.author)}


def _post_detail(p, request):
    return {**post_summary(p), "body": p.body, "html": render(p.body),
            "updated_at": p.updated_at.isoformat(), "can_edit": can_edit(request)}


def _apply(post, data):
    title = (data.get("title") or "").strip()
    if not title:
        return "A post needs a title."
    try:
        post.date = date.fromisoformat(data.get("date") or timezone.localdate().isoformat())
    except ValueError:
        return "Date must be YYYY-MM-DD."
    post.title = title
    post.body = data.get("body") or ""
    post.published = bool(data.get("published", True))
    return None


def blog_list(request):
    if request.method == "POST":
        denied = editor_only(request)
        if denied:
            return denied
        data = json_body(request)
        if data is None:
            return bad_request("Invalid JSON.")
        post = Post(author=request.user)
        err = _apply(post, data)
        if err:
            return bad_request(err)
        post.save()
        return JsonResponse({"status": "success", "id": post.id}, status=201)

    posts = _visible_posts(request)
    q = (request.GET.get("q") or "").strip()
    if q:
        posts = posts.filter(Q(title__icontains=q) | Q(body__icontains=q))
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1
    total = posts.count()
    chunk = posts[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    return JsonResponse({"posts": [post_summary(p) for p in chunk], "page": page,
                         "pages": max(1, -(-total // PAGE_SIZE)), "total": total,
                         "can_edit": can_edit(request)})


def blog_post(request, post_id):
    post = _visible_posts(request).filter(id=post_id).first()
    if not post:
        return JsonResponse({"error": "Not found"}, status=404)
    if request.method == "GET":
        return JsonResponse(_post_detail(post, request))

    denied = editor_only(request)
    if denied:
        return denied
    if request.method == "DELETE":
        post.delete()
        return JsonResponse({"status": "success"})
    if request.method not in ("POST", "PUT"):
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    data = json_body(request)
    if data is None:
        return bad_request("Invalid JSON.")
    err = _apply(post, data)
    if err:
        return bad_request(err)
    post.save()
    return JsonResponse({"status": "success", "id": post.id})


def _exif_taken_at(img):
    try:
        raw = img.getexif().get_ifd(0x8769).get(36867) or img.getexif().get(306)  # DateTimeOriginal / DateTime
        return timezone.make_aware(datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")) if raw else None
    except Exception:
        return None


def photo_upload(request):
    """Multipart upload (field "photo"): resize, save to the data drive, return its URL."""
    denied = editor_only(request)
    if denied:
        return denied
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST a file"}, status=405)
    f = request.FILES.get("photo")
    if not f:
        return bad_request("No photo in the upload.")
    if f.size > MAX_UPLOAD_BYTES:
        return bad_request("Photo is larger than 25 MB.")

    from PIL import Image, ImageOps, UnidentifiedImageError  # heavy import: only when needed

    try:
        img = Image.open(f)
        taken_at = _exif_taken_at(img)
        img = ImageOps.exif_transpose(img)
        img.thumbnail((MAX_PHOTO_EDGE, MAX_PHOTO_EDGE))
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError):
        return bad_request("That file isn't a picture I can read (JPEG, PNG, WebP…).")

    now = timezone.localtime()
    rel = f"photos/{now:%Y/%m}/{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.jpg"
    dest = settings.MEDIA_ROOT / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "JPEG", quality=85, optimize=True)

    caption = (request.POST.get("caption") or "").strip()
    photo = Photo.objects.create(file=rel, original_name=f.name[:255], caption=caption,
                                 width=img.width, height=img.height, taken_at=taken_at,
                                 uploaded_by=request.user)
    alt = caption or "photo"
    return JsonResponse({"status": "success", "id": photo.id, "url": photo.url,
                         "markdown": f"![{alt}]({photo.url})",
                         "width": img.width, "height": img.height}, status=201)
