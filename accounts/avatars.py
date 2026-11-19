# Garden-character avatars: client/static/avatars/<slug>.svg (original art,
# vendored so they work on the offline hotspot).
AVATARS = [
    ("tomato", "Tomato"), ("carrot", "Carrot"), ("radish", "Radish"), ("pea", "Pea pod"),
    ("sunflower", "Sunflower"), ("bee", "Bee"), ("ladybug", "Ladybug"), ("snail", "Snail"),
    ("mushroom", "Mushroom"), ("pumpkin", "Pumpkin"), ("frog", "Frog"), ("cactus", "Cactus"),
    ("strawberry", "Strawberry"), ("worm", "Worm"), ("chick", "Chick"), ("eggplant", "Eggplant"),
]
AVATAR_SLUGS = [slug for slug, _ in AVATARS]


def avatar_url(slug):
    return f"/static/avatars/{slug if slug in AVATAR_SLUGS else AVATAR_SLUGS[0]}.svg"
