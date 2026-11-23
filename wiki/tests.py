import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from config.markup import render, wiki_links

from .models import WikiPage


class MarkupTests(TestCase):
    def test_wiki_links_and_sanitising(self):
        html = render("See [[Tomato Beds|the beds]] <script>alert(1)</script> **bold**")
        self.assertIn('href="#/wiki/tomato-beds"', html)
        self.assertIn(">the beds</a>", html)
        self.assertNotIn("<script", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertEqual(wiki_links("[[A b]] and [[C|d]]"), {"a-b", "c"})

    def test_javascript_links_are_dropped(self):
        self.assertNotIn("javascript:", render("[x](javascript:alert(1))"))


class WikiApiTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("admin", "", "pw")

    def put(self, slug, **data):
        return self.client.put(f"/api/wiki/{slug}/", json.dumps(data), content_type="application/json")

    def test_editing_requires_staff(self):
        self.assertEqual(self.put("heater", title="Heater", body="x").status_code, 403)

    def test_create_edit_keeps_revision_and_backlinks(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.put("heater", title="Heater", body="v1").status_code, 200)
        self.put("heater", title="Heater", body="v2")
        self.put("checklist", title="Checklist", body="Check the [[Heater]]")
        page = WikiPage.objects.get(slug="heater")
        self.assertEqual(page.body, "v2")
        self.assertEqual(page.revisions.get().body, "v1")

        self.client.logout()
        d = self.client.get("/api/wiki/heater/").json()
        self.assertEqual(d["backlinks"], [{"slug": "checklist", "title": "Checklist"}])
        self.assertFalse(d["can_edit"])
        self.assertEqual(self.client.get("/api/wiki/missing/").status_code, 404)
