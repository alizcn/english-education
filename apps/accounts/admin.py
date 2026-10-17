from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserConsent, UserLevel


class UserLevelInline(admin.StackedInline):
    model = UserLevel
    extra = 0
    readonly_fields = ('updated_at',)


class UserConsentInline(admin.TabularInline):
    model = UserConsent
    extra = 0
    readonly_fields = ('kind', 'accepted_at', 'ip_address', 'user_agent')
    can_delete = False


class CustomUserAdmin(BaseUserAdmin):
    inlines = [UserLevelInline, UserConsentInline]
    list_display = ('username', 'email', 'is_superuser', 'is_active', 'date_joined', 'last_login')
    list_filter = ('is_superuser', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('-date_joined',)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserLevel)
class UserLevelAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_level', 'score', 'updated_at')
    list_filter = ('current_level',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('updated_at',)


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = ('user', 'kind', 'accepted_at', 'ip_address')
    list_filter = ('kind',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('accepted_at',)
