from django import forms
from django.conf import settings

from accounts import choices as c
from listings.models import Listing

MAX_R = settings.CHEERIPICK["MAX_RADIUS_KM"]


class DiscoverFilterForm(forms.Form):
    SORT_CHOICES = [
        ("best", "Best match"),
        ("nearest", "Nearest"),
        ("newest", "Newest"),
        ("rent", "Lowest rent"),
    ]
    radius = forms.IntegerField(
        label="Distance (km)", min_value=1, max_value=MAX_R, required=False,
        widget=forms.NumberInput(attrs={"type": "range", "min": 1, "max": MAX_R, "data-range-output": "radius-out"}),
    )
    budget_min = forms.IntegerField(label="Budget from", min_value=0, required=False,
                                    widget=forms.NumberInput(attrs={"step": 500, "placeholder": "min"}))
    budget_max = forms.IntegerField(label="to", min_value=0, required=False,
                                    widget=forms.NumberInput(attrs={"step": 500, "placeholder": "max"}))
    move_in = forms.DateField(label="Move-in around", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    role = forms.ChoiceField(
        label="Show me", required=False,
        choices=[("", "Everyone"), (c.ROLE_HOST, "Hosts (have a room)"), (c.ROLE_SEEKER, "Seekers")],
    )
    room_type = forms.ChoiceField(label="Room type", required=False, choices=[("", "Any")] + Listing.ROOM_TYPE_CHOICES)
    verified_only = forms.BooleanField(label="Verified only ✅", required=False)
    has_photos = forms.BooleanField(label="Has photos 📸", required=False)
    sort = forms.ChoiceField(label="Sort by", choices=SORT_CHOICES, required=False)

    def clean(self):
        data = super().clean()
        lo, hi = data.get("budget_min"), data.get("budget_max")
        if lo is not None and hi is not None and lo > hi:
            data["budget_min"], data["budget_max"] = hi, lo
        return data

    def to_filters(self, viewer):
        """Translate cleaned form data into algorithm filters."""
        d = self.cleaned_data if self.is_valid() else {}
        lo = d.get("budget_min")
        hi = d.get("budget_max")
        budget = None
        if lo is not None or hi is not None:
            budget = (
                lo if lo is not None else (viewer.budget_min or 0),
                hi if hi is not None else (viewer.budget_max or 10**9),
            )
        return {
            "budget": budget,
            "move_in": d.get("move_in"),
            "role": d.get("role") or None,
            "room_type": d.get("room_type") or None,
            "verified_only": d.get("verified_only", False),
            "has_photos": d.get("has_photos", False),
        }
