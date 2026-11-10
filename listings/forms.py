from django import forms
from django.conf import settings

from accounts.images import MultipleImageField

from .models import Amenity, Listing

MAX_PHOTOS = settings.CHEERIPICK["MAX_LISTING_PHOTOS"]


class ListingForm(forms.ModelForm):
    amenities = forms.ModelMultipleChoiceField(
        queryset=Amenity.objects.all(), widget=forms.CheckboxSelectMultiple, required=False
    )
    new_photos = MultipleImageField(label="Add photos", help_text=f"Up to {MAX_PHOTOS} total · JPG/PNG/WEBP · 5 MB max")

    class Meta:
        model = Listing
        fields = [
            "title", "description", "rent", "deposit", "room_type", "furnished", "amenities",
            "available_from", "address", "latitude", "longitude", "house_rules",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Sunny room in a chill 3BHK"}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "What's the flat like? Who lives there?"}),
            "house_rules": forms.Textarea(attrs={"rows": 3, "placeholder": "No loud music after 11, shared cleaning on Sundays..."}),
            "room_type": forms.RadioSelect,
            "furnished": forms.RadioSelect,
            "available_from": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "latitude": forms.HiddenInput,
            "longitude": forms.HiddenInput,
            "rent": forms.NumberInput(attrs={"step": 500}),
            "deposit": forms.NumberInput(attrs={"step": 500}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.existing_photos = self.instance.photos.count() if self.instance.pk else 0

    def clean_new_photos(self):
        photos = self.cleaned_data.get("new_photos") or []
        if self.existing_photos + len(photos) > MAX_PHOTOS:
            raise forms.ValidationError(f"Max {MAX_PHOTOS} photos per listing (you have {self.existing_photos}).")
        return photos

    def clean_deposit(self):
        deposit = self.cleaned_data.get("deposit") or 0
        return deposit
