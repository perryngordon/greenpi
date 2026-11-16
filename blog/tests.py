import io
import json
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from PIL import Image

from .models import Photo, Post


class BlogApiTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("admin", "", "pw")

    def post_json(self, url, data):
        return self.client.post(url, json.dumps(data), content_type="application/json")

    def test_create_requires_staff(self):
        self.assertEqual(self.post_json("/api/blog/", {"title": "x"}).status_code, 403)

    def test_drafts_hidden_from_public(self):
        self.client.force_login(self.admin)
        self.post_json("/api/blog/", {"title": "Seen", "date": "2026-11-16", "body": "hi"})
        self.post_json("/api/blog/", {"title": "Draft", "date": "2026-11-16", "published": False})
        self.assertEqual(self.client.get("/api/blog/").json()["total"], 2)
        self.client.logout()
        posts = self.client.get("/api/blog/").json()["posts"]
        self.assertEqual([p["title"] for p in posts], ["Seen"])
        draft = Post.objects.get(title="Draft")
        self.assertEqual(self.client.get(f"/api/blog/{draft.id}/").status_code, 404)

    def test_bad_date_rejected(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.post_json("/api/blog/", {"title": "x", "date": "16/11"}).status_code, 400)


class PhotoUploadTests(TestCase):
    def setUp(self):
        self.media = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.media)
        self.admin = get_user_model().objects.create_superuser("admin", "", "pw")

    def test_upload_resizes_and_stores(self):
        buf = io.BytesIO()
        Image.new("RGB", (4000, 3000), "green").save(buf, "JPEG")
        buf.name = "big.jpg"
        buf.seek(0)
        self.client.force_login(self.admin)
        with override_settings(MEDIA_ROOT=self.media):
            r = self.client.post("/api/photos/", {"photo": buf, "caption": "Seedlings"})
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertEqual((d["width"], d["height"]), (2000, 1500))
        self.assertTrue(d["markdown"].startswith("![Seedlings](/media/photos/"))
        photo = Photo.objects.get()
        self.assertTrue((self.media / photo.file).exists())

    def test_non_image_rejected(self):
        self.client.force_login(self.admin)
        bad = io.BytesIO(b"not an image")
        bad.name = "x.jpg"
        with override_settings(MEDIA_ROOT=self.media):
            self.assertEqual(self.client.post("/api/photos/", {"photo": bad}).status_code, 400)
