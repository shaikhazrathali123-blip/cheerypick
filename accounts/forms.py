import re

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from . import choices as c
from .cities import lookup_city
from .images import MultipleImageField
from .models import Interest, Report, User

CFG = settings.CHEERIPICK


def _drop_blank_choice(field):
    """RadioSelect on blank=True model fields shows an ugly '------' option."""
    field.choices = [(k, v) for k, v in field.choices if k not in ("", None)]


class SignUpForm(UserCreationForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "you@email.com", "autocomplete": "email"}))
    is_adult = forms.BooleanField(label="I'm 18 or older", required=True)

    class Meta:
        model = User
        fields = ("username", "email")
        widgets = {"username": forms.TextInput(attrs={"placeholder": "pick a handle"})}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("That email already has an account. Try logging in?")
        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email or username",
        widget=forms.TextInput(attrs={"autofocus": True, "placeholder": "you@email.com"}),
    )


# --- Onboarding wizard ------------------------------------------------------
class BasicsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["role", "name", "age", "gender", "pronouns", "occupation", "bio"]
        widgets = {
            "role": forms.RadioSelect,
            "gender": forms.RadioSelect,
            "occupation": forms.RadioSelect,
            "bio": forms.Textarea(attrs={"rows": 3, "maxlength": 300, "placeholder": "Plant parent, chai addict, 10pm gym person..."}),
            "name": forms.TextInput(attrs={"placeholder": "What should people call you?"}),
            "pronouns": forms.TextInput(attrs={"placeholder": "she/her, he/him, they/them..."}),
        }
        labels = {"role": "I'm here because...", "name": "First name", "bio": "Short bio"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ("name", "age", "gender", "occupation"):
            self.fields[f].required = True
        for f in ("gender", "occupation"):
            _drop_blank_choice(self.fields[f])

    def clean_age(self):
        age = self.cleaned_data.get("age")
        if age is not None and age < 18:
            raise forms.ValidationError("CheeriPick is 18+ only.")
        return age


class LocationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["city", "latitude", "longitude", "search_radius_km"]
        widgets = {
            "latitude": forms.HiddenInput,
            "longitude": forms.HiddenInput,
            "city": forms.TextInput(attrs={"placeholder": "e.g. Bengaluru", "data-city-input": ""}),
            "search_radius_km": forms.NumberInput(
                attrs={"type": "range", "min": 1, "max": CFG["MAX_RADIUS_KM"], "data-range-output": "radius-out"}
            ),
        }
        labels = {"search_radius_km": "How far are you willing to look? (km)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].required = True

    def clean(self):
        data = super().clean()
        lat, lon = data.get("latitude"), data.get("longitude")
        if lat is not None and not -90 <= lat <= 90:
            self.add_error(None, "Latitude looks off.")
        if lon is not None and not -180 <= lon <= 180:
            self.add_error(None, "Longitude looks off.")
        if lat is None or lon is None:
            coords = lookup_city(data.get("city"))
            if coords:
                data["latitude"], data["longitude"] = coords
            else:
                self.add_error(
                    "city",
                    "We couldn't pin that city. Tap “Use my location” or try a big city nearby.",
                )
        return data


class BudgetForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["budget_min", "budget_max", "move_in_date", "stay_months"]
        widgets = {
            "move_in_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "budget_min": forms.NumberInput(attrs={"step": 500, "placeholder": "8000"}),
            "budget_max": forms.NumberInput(attrs={"step": 500, "placeholder": "15000"}),
        }
        labels = {
            "budget_min": "Min monthly rent",
            "budget_max": "Max monthly rent",
            "move_in_date": "Move-in date",
            "stay_months": "How long do you want to stay? (months)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = True

    def clean(self):
        data = super().clean()
        lo, hi = data.get("budget_min"), data.get("budget_max")
        if lo is not None and hi is not None and lo > hi:
            self.add_error("budget_max", "Max should be at least your min 😅")
        return data


class VibeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = c.VIBE_FIELDS
        widgets = {f: forms.RadioSelect for f in c.VIBE_FIELDS}
        labels = {
            "sleep_schedule": "Sleep schedule",
            "cleanliness": "How tidy are you? (1 = chaos, 5 = spotless)",
            "noise_tolerance": "Noise tolerance (1 = library, 5 = festival)",
            "guests_frequency": "How often do you have people over?",
            "smoking": "Smoking",
            "drinking": "Drinking",
            "pets": "Pets",
            "food_habits": "Food habits",
            "work_from_home": "Work / study from home?",
            "social_style": "Roommate energy",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.required = True
            _drop_blank_choice(field)


class InterestsForm(forms.ModelForm):
    interests = forms.ModelMultipleChoiceField(
        queryset=Interest.objects.all(), widget=forms.CheckboxSelectMultiple, required=False,
        help_text="Pick at least 3 — it helps your matches a lot.",
    )
    dealbreakers = forms.MultipleChoiceField(
        choices=c.DEALBREAKER_CHOICES, widget=forms.CheckboxSelectMultiple, required=False,
        help_text=f"Up to {CFG['MAX_DEALBREAKERS']}. People who don't match these won't show up at all.",
    )

    class Meta:
        model = User
        fields = ["interests", "dealbreakers", "preferred_gender", "preferred_gender_value"]
        widgets = {"preferred_gender": forms.RadioSelect}
        labels = {"preferred_gender": "Roommate gender preference"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["preferred_gender_value"].required = False

    def clean_dealbreakers(self):
        picks = self.cleaned_data.get("dealbreakers") or []
        if len(picks) > CFG["MAX_DEALBREAKERS"]:
            raise forms.ValidationError(f"Max {CFG['MAX_DEALBREAKERS']} dealbreakers — keep it to what really matters.")
        return picks

    def clean(self):
        data = super().clean()
        if data.get("preferred_gender") == c.PREF_GENDER_SPECIFIC and not data.get("preferred_gender_value"):
            self.add_error("preferred_gender_value", "Pick which gender.")
        if data.get("preferred_gender") != c.PREF_GENDER_SPECIFIC:
            data["preferred_gender_value"] = ""
        return data


class PhotoUploadForm(forms.Form):
    photos = MultipleImageField(label="Add photos", help_text="JPG, PNG or WEBP · max 5 MB each")

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_photos(self):
        photos = self.cleaned_data.get("photos") or []
        existing = self.user.photos.count() if self.user else 0
        limit = CFG["MAX_PROFILE_PHOTOS"]
        if existing + len(photos) > limit:
            raise forms.ValidationError(f"You can have up to {limit} photos (you have {existing}).")
        return photos


# Ordered wizard steps: (slug, title, subtitle, form class)
ONBOARDING_STEPS = [
    ("basics", "The basics", "Let's start simple 👋", BasicsForm),
    ("location", "Where you at?", "We only use this to find people nearby 📍", LocationForm),
    ("budget", "Money & timing", "No awkward rent convos later 💸", BudgetForm),
    ("vibe", "Your vibe", "Be honest — it's how we find your people", VibeForm),
    ("interests", "Interests & dealbreakers", "The stuff that makes or breaks it", InterestsForm),
    ("photos", "Show your face", "Profiles with photos get way more matches 📸", PhotoUploadForm),
]


# --- Settings / safety ------------------------------------------------------
class RoleSwitchForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["role"]
        widgets = {"role": forms.RadioSelect}
        labels = {"role": "Your role"}


class PhoneForm(forms.Form):
    phone = forms.CharField(max_length=20, widget=forms.TextInput(attrs={"placeholder": "+91 98765 43210", "inputmode": "tel"}))

    def clean_phone(self):
        raw = self.cleaned_data["phone"]
        digits = re.sub(r"[^\d+]", "", raw)
        if not re.fullmatch(r"\+?\d{8,15}", digits):
            raise forms.ValidationError("That number looks off.")
        return digits


class OtpForm(forms.Form):
    code = forms.CharField(max_length=6, min_length=6, widget=forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "123456"}))


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        widgets = {"details": forms.Textarea(attrs={"rows": 2, "placeholder": "Anything we should know? (optional)"})}
