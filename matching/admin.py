from django.contrib import admin

from .models import Match, Swipe


@admin.register(Swipe)
class SwipeAdmin(admin.ModelAdmin):
    list_display = ("from_user", "action", "to_user", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("from_user__username", "to_user__username")
    list_select_related = ("from_user", "to_user")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("user_a", "user_b", "score", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user_a__username", "user_b__username", "user_a__email", "user_b__email")
    list_select_related = ("user_a", "user_b")
