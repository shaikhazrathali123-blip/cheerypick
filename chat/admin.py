from django.contrib import admin

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("sender", "match", "short_body", "created_at", "read_at")
    list_filter = ("created_at", "read_at")
    search_fields = ("body", "sender__username", "sender__email")
    list_select_related = ("sender", "match__user_a", "match__user_b")
    raw_id_fields = ("match", "sender")

    @admin.display(description="Message")
    def short_body(self, obj):
        return obj.body[:60]
