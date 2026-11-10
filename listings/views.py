from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.images import process_image
from accounts.models import Block

from .forms import ListingForm
from .models import Listing, ListingPhoto


def _host_required(request):
    if not request.user.is_host:
        messages.info(request, "Switch your role to “I have a room” in settings to post listings 🏠")
        return redirect("accounts:settings")
    return None


@login_required
def my_listings(request):
    listings = (
        Listing.objects.filter(host=request.user)
        .prefetch_related("photos", "amenities")
        .order_by("status", "-created_at")
    )
    return render(request, "listings/my_listings.html", {"listings": listings})


def _save_photos(listing, files):
    start = listing.photos.count()
    for i, f in enumerate(files):
        ListingPhoto.objects.create(listing=listing, image=process_image(f), order=start + i)


@login_required
def listing_create(request):
    gate = _host_required(request)
    if gate:
        return gate
    form = ListingForm(request.POST or None, request.FILES or None,
                       initial={"latitude": request.user.latitude, "longitude": request.user.longitude})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            listing = form.save(commit=False)
            listing.host = request.user
            if listing.latitude is None:
                listing.latitude, listing.longitude = request.user.latitude, request.user.longitude
            listing.save()
            form.save_m2m()
            _save_photos(listing, form.cleaned_data["new_photos"])
        messages.success(request, "Listing is live! 🎉")
        return redirect("listings:detail", pk=listing.pk)
    return render(request, "listings/listing_form.html", {"form": form, "is_edit": False})


@login_required
def listing_edit(request, pk):
    listing = get_object_or_404(Listing.objects.prefetch_related("photos"), pk=pk, host=request.user)
    form = ListingForm(request.POST or None, request.FILES or None, instance=listing)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            _save_photos(listing, form.cleaned_data["new_photos"])
        messages.success(request, "Saved ✨")
        return redirect("listings:detail", pk=listing.pk)
    return render(request, "listings/listing_form.html", {"form": form, "is_edit": True, "listing": listing})


@login_required
@require_POST
def listing_toggle(request, pk):
    listing = get_object_or_404(Listing, pk=pk, host=request.user)
    listing.status = Listing.STATUS_PAUSED if listing.is_active else Listing.STATUS_ACTIVE
    listing.save(update_fields=["status", "updated_at"])
    messages.info(request, "Listing paused ⏸️" if not listing.is_active else "Listing is live again ▶️")
    return redirect("listings:mine")


@login_required
def listing_delete(request, pk):
    listing = get_object_or_404(Listing, pk=pk, host=request.user)
    if request.method == "POST":
        for p in listing.photos.all():
            p.delete()
        listing.delete()
        messages.info(request, "Listing deleted.")
        return redirect("listings:mine")
    return render(request, "listings/listing_confirm_delete.html", {"listing": listing})


@login_required
@require_POST
def listing_photo_delete(request, pk):
    photo = get_object_or_404(ListingPhoto, pk=pk, listing__host=request.user)
    listing_id = photo.listing_id
    photo.delete()
    return redirect("listings:edit", pk=listing_id)


@login_required
def listing_detail(request, pk):
    listing = get_object_or_404(
        Listing.objects.select_related("host").prefetch_related("photos", "amenities", "host__photos"), pk=pk
    )
    is_owner = listing.host_id == request.user.pk
    if not is_owner:
        if not listing.is_active or listing.host.is_under_review:
            raise Http404
        if Block.objects.filter(blocker=listing.host, blocked=request.user).exists() or \
                Block.objects.filter(blocker=request.user, blocked=listing.host).exists():
            raise Http404
    return render(request, "listings/listing_detail.html", {"listing": listing, "is_owner": is_owner})
