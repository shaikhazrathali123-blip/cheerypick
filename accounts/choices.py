"""
All the choice lists for profiles live here so models, forms, the matching
algorithm and the seed command speak the same language.
"""

ROLE_HOST = "host"
ROLE_SEEKER = "seeker"
ROLE_CHOICES = [
    (ROLE_SEEKER, "Looking for a room"),
    (ROLE_HOST, "I have a room"),
]

GENDER_CHOICES = [
    ("woman", "Woman"),
    ("man", "Man"),
    ("nonbinary", "Non-binary"),
    ("other", "Other"),
]

OCCUPATION_CHOICES = [
    ("student", "Student"),
    ("working", "Working"),
    ("freelancer", "Freelancer"),
    ("other", "Other"),
]

PREF_GENDER_ANY = "any"
PREF_GENDER_SAME = "same"
PREF_GENDER_SPECIFIC = "specific"
PREFERRED_GENDER_CHOICES = [
    (PREF_GENDER_ANY, "Anyone"),
    (PREF_GENDER_SAME, "Same as me"),
    (PREF_GENDER_SPECIFIC, "Specific gender"),
]

SCALE_CHOICES = [(i, str(i)) for i in range(1, 6)]

SLEEP_CHOICES = [
    ("early", "Early bird"),
    ("night", "Night owl"),
    ("flexible", "Flexible"),
]
GUESTS_CHOICES = [
    ("rarely", "Rarely"),
    ("sometimes", "Sometimes"),
    ("often", "Often"),
]
SMOKING_CHOICES = [
    ("no", "No"),
    ("outside", "Outside only"),
    ("yes", "Yes"),
]
DRINKING_CHOICES = [
    ("no", "No"),
    ("socially", "Socially"),
    ("often", "Often"),
]
PETS_CHOICES = [
    ("have", "Have pets"),
    ("okay", "Okay with pets"),
    ("no", "No pets"),
]
FOOD_CHOICES = [
    ("veg", "Veg"),
    ("nonveg", "Non-veg"),
    ("vegan", "Vegan"),
    ("any", "Anything goes"),
]
WFH_CHOICES = [
    ("yes", "Work from home"),
    ("no", "Out all day"),
    ("hybrid", "Hybrid"),
]
SOCIAL_CHOICES = [
    ("private", "Keep to myself"),
    ("friendly", "Friendly"),
    ("besties", "Let's be besties"),
]

# Lifestyle "vibe" fields. Scale fields are 1–5 numbers, choice fields are options.
VIBE_SCALE_FIELDS = ["cleanliness", "noise_tolerance"]
VIBE_CHOICE_FIELDS = [
    "sleep_schedule",
    "guests_frequency",
    "smoking",
    "drinking",
    "pets",
    "food_habits",
    "work_from_home",
    "social_style",
]
VIBE_FIELDS = VIBE_SCALE_FIELDS + VIBE_CHOICE_FIELDS

VIBE_FIELD_LABELS = {
    "sleep_schedule": "Sleep schedule",
    "cleanliness": "Cleanliness",
    "noise_tolerance": "Noise tolerance",
    "guests_frequency": "Guests",
    "smoking": "Smoking",
    "drinking": "Drinking",
    "pets": "Pets",
    "food_habits": "Food",
    "work_from_home": "Work from home",
    "social_style": "Social style",
}
DEALBREAKER_CHOICES = [(f, VIBE_FIELD_LABELS[f]) for f in VIBE_FIELDS]

# Copy for "why you matched" when both people share the same value.
# Keys are (field, value). Missing pairs fall back to a generic line.
SHARED_VIBE_REASONS = {
    ("sleep_schedule", "night"): "Both night owls 🌙",
    ("sleep_schedule", "early"): "Both early birds 🌅",
    ("sleep_schedule", "flexible"): "Both flexible sleepers 😴",
    ("smoking", "no"): "Both smoke-free 🚭",
    ("smoking", "outside"): "Both smoke outside only",
    ("drinking", "no"): "Both sober-living 🧃",
    ("drinking", "socially"): "Both social drinkers 🥂",
    ("drinking", "often"): "Both up for drinks 🍻",
    ("pets", "have"): "Both pet parents 🐾",
    ("pets", "okay"): "Both cool with pets 🐶",
    ("pets", "no"): "Both prefer no pets",
    ("food_habits", "veg"): "Both vegetarian 🥗",
    ("food_habits", "vegan"): "Both vegan 🌱",
    ("food_habits", "nonveg"): "Both non-veg foodies 🍗",
    ("food_habits", "any"): "Both eat anything 🍜",
    ("work_from_home", "yes"): "Both WFH 💻",
    ("work_from_home", "hybrid"): "Both on a hybrid schedule",
    ("work_from_home", "no"): "Both out during the day",
    ("social_style", "besties"): "Both want a roommate-bestie 👯",
    ("social_style", "friendly"): "Both friendly but chill 🙂",
    ("social_style", "private"): "Both value their space 🎧",
    ("guests_frequency", "rarely"): "Both rarely have guests 🏠",
    ("guests_frequency", "sometimes"): "Same take on guests",
    ("guests_frequency", "often"): "Both love hosting 🎉",
}

# Interests seeded by a data migration: (slug, name, emoji)
DEFAULT_INTERESTS = [
    ("gaming", "Gaming", "🎮"),
    ("gym", "Gym", "💪"),
    ("music", "Music", "🎧"),
    ("cooking", "Cooking", "🍳"),
    ("anime", "Anime", "🍥"),
    ("travel", "Travel", "✈️"),
    ("reading", "Reading", "📚"),
    ("movies", "Movies", "🎬"),
    ("art", "Art", "🎨"),
    ("tech", "Tech", "💻"),
    ("yoga", "Yoga", "🧘"),
    ("football", "Football", "⚽"),
    ("cricket", "Cricket", "🏏"),
    ("photography", "Photography", "📷"),
    ("plants", "Plants", "🪴"),
    ("hiking", "Hiking", "🥾"),
    ("dance", "Dance", "💃"),
    ("podcasts", "Podcasts", "🎙️"),
    ("fashion", "Fashion", "👗"),
    ("coffee", "Coffee", "☕"),
]
