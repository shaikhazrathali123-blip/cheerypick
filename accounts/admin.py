from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import Block, Interest, ProfilePhoto, Report, User


class ProfilePhotoInline(admin.TabularInline):
    model = ProfilePhoto
    extra = 0
    fields = ("preview", "image", "order")
    readonly_fields = ("preview",)

    @admin.display(description="Preview")
    def preview(self, obj):
        return format_html('<img src="{}" style="height:60px;border-radius:8px">', obj.image.url) if obj.image else "—"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [ProfilePhotoInline]
    list_display = (
        "username", "name", "email", "role", "city", "profile_completion", "trust_score",
        "email_verified", "is_under_review", "is_hidden_inactive", "last_active",
    )
    list_filter = (
        "role", "email_verified", "phone_verified", "is_under_review", "is_hidden_inactive",
        "gender", "occupation", "is_staff", "is_active",
    )
    search_fields = ("username", "email", "name", "city", "phone")
    filter_horizontal = ("interests", "groups", "user_permissions")
    readonly_fields = ("profile_completion", "trust_score", "last_active", "date_joined", "last_login")
    actions = ["clear_review", "mark_email_verified", "refresh_scores"]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {"fields": ("role", "name", "age", "gender", "pronouns", "occupation", "bio")}),
        ("Location", {"fields": ("city", "latitude", "longitude", "search_radius_km")}),
        ("Budget & timing", {"fields": ("budget_min", "budget_max", "move_in_date", "stay_months")}),
        ("Vibe", {"fields": (
            "sleep_schedule", "cleanliness", "noise_tolerance", "guests_frequency", "smoking",
            "drinking", "pets", "food_habits", "work_from_home", "social_style",
        )}),
        ("Matching prefs", {"fields": ("interests", "dealbreakers", "preferred_gender", "preferred_gender_value")}),
        ("Trust & safety", {"fields": (
            "email_verified", "phone", "phone_verified", "is_under_review", "is_hidden_inactive",
            "profile_completion", "trust_score", "last_active",
        )}),
    )

    @admin.action(description="Clear review (un-hide) and resolve their reports")
    def clear_review(self, request, queryset):
        Report.objects.filter(reported__in=queryset).update(resolved=True)
        n = queryset.update(is_under_review=False)
        self.message_user(request, f"{n} profile(s) restored.", messages.SUCCESS)

    @admin.action(description="Mark email verified")
    def mark_email_verified(self, request, queryset):
        queryset.update(email_verified=True)

    @admin.action(description="Recompute completion + trust score")
    def refresh_scores(self, request, queryset):
        for u in queryset:
            u.refresh_stats()


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ("name", "emoji", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProfilePhoto)
class ProfilePhotoAdmin(admin.ModelAdmin):
    list_display = ("user", "order", "uploaded_at")
    search_fields = ("user__username", "user__email")
    list_select_related = ("user",)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reported", "reporter", "reason", "resolved", "created_at")
    list_filter = ("reason", "resolved", "created_at")
    search_fields = ("reported__username", "reported__email", "reporter__username", "details")
    list_select_related = ("reported", "reporter")
    actions = ["mark_resolved"]

    @admin.action(description="Mark resolved")
    def mark_resolved(self, request, queryset):
        queryset.update(resolved=True)


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    search_fields = ("blocker__username", "blocked__username")
    list_filter = ("created_at",)
    list_select_related = ("blocker", "blocked")
