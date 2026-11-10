from django.contrib import admin

from .models import Amenity, Listing, ListingPhoto


class ListingPhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "host", "rent", "room_type", "furnished", "status", "available_from", "created_at")
    list_filter = ("status", "room_type", "furnished", "amenities", "available_from")
    search_fields = ("title", "description", "address", "host__username", "host__email")
    list_select_related = ("host",)
    filter_horizontal = ("amenities",)
    inlines = [ListingPhotoInline]
    actions = ["pause", "activate"]

    @admin.action(description="Pause selected listings")
    def pause(self, request, queryset):
        queryset.update(status=Listing.STATUS_PAUSED)

    @admin.action(description="Activate selected listings")
    def activate(self, request, queryset):
        queryset.update(status=Listing.STATUS_ACTIVE)


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ("name", "emoji", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ListingPhoto)
class ListingPhotoAdmin(admin.ModelAdmin):
    list_display = ("listing", "order")
    search_fields = ("listing__title",)
    list_select_related = ("listing",)
