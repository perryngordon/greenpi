from django.db.models import Q
from django.http import JsonResponse

from config.api import bad_request, is_staff, json_body, staff_only
from config.markup import excerpt, render, wiki_links, wiki_slug

from .models import WikiPage, WikiRevision


def _page_summary(p):
    return {"slug": p.slug, "title": p.title, "updated_at": p.updated_at.isoformat(),
            "excerpt": excerpt(p.body, 160)}


def wiki_list(request):
    pages = WikiPage.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        pages = pages.filter(Q(title__icontains=q) | Q(body__icontains=q))
    return JsonResponse({"pages": [_page_summary(p) for p in pages], "can_edit": is_staff(request)})


def _backlinks(slug):
    """Wiki pages and blog posts that link to [[this page]]."""
    from blog.models import Post  # avoid an import cycle at module load

    pages = [p for p in WikiPage.objects.filter(body__contains="[[").exclude(slug=slug)
             if slug in wiki_links(p.body)]
    posts = [p for p in Post.objects.filter(published=True, body__contains="[[")
             if slug in wiki_links(p.body)]
    return (
        [{"slug": p.slug, "title": p.title} for p in pages],
        [{"id": p.id, "title": p.title, "date": p.date.isoformat()} for p in posts],
    )


def wiki_page(request, slug):
    if request.method == "GET":
        page = WikiPage.objects.filter(slug=slug).first()
        if not page:
            return JsonResponse({"exists": False, "slug": slug,
                                 "title": slug.replace("-", " ").title(),
                                 "can_edit": is_staff(request)}, status=404)
        backlink_pages, backlink_posts = _backlinks(slug)
        return JsonResponse({
            "exists": True, "slug": page.slug, "title": page.title,
            "body": page.body, "html": render(page.body),
            "updated_at": page.updated_at.isoformat(),
            "revisions": page.revisions.count(),
            "backlinks": backlink_pages, "posts": backlink_posts,
            "can_edit": is_staff(request),
        })

    denied = staff_only(request)
    if denied:
        return denied

    if request.method == "DELETE":
        WikiPage.objects.filter(slug=slug).delete()
        return JsonResponse({"status": "success"})

    if request.method not in ("POST", "PUT"):
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)
    data = json_body(request)
    if data is None:
        return bad_request("Invalid JSON.")
    title = (data.get("title") or "").strip()
    body = data.get("body") or ""
    if not title:
        return bad_request("A page needs a title.")

    page = WikiPage.objects.filter(slug=slug).first()
    if page:
        if page.title != title or page.body != body:
            WikiRevision.objects.create(page=page, title=page.title, body=page.body,
                                        created_by=page.updated_by)
        page.title, page.body, page.updated_by = title, body, request.user
        page.save()
    else:
        page = WikiPage.objects.create(slug=wiki_slug(slug), title=title, body=body,
                                       updated_by=request.user)
    return JsonResponse({"status": "success", "slug": page.slug})


def wiki_history(request, slug):
    page = WikiPage.objects.filter(slug=slug).first()
    if not page:
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse({"slug": slug, "revisions": [
        {"id": r.id, "title": r.title, "created_at": r.created_at.isoformat(),
         "by": r.created_by.get_username() if r.created_by else None,
         "body": r.body if is_staff(request) else None}
        for r in page.revisions.all()[:50]
    ]})
