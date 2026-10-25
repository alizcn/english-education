from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserConsent, UserCourse


class UserCourseInline(admin.TabularInline):
    # TabularInline, StackedInline değil: kullanıcının artık birden çok kursu
    # olabiliyor ve yığılmış form her kurs için bir ekran yer kaplıyordu.
    model = UserCourse
    extra = 0
    fields = ('target_language', 'native_language', 'current_level', 'score',
              'is_active', 'updated_at')
    readonly_fields = ('updated_at',)


class UserConsentInline(admin.TabularInline):
    model = UserConsent
    extra = 0
    readonly_fields = ('kind', 'accepted_at', 'ip_address', 'user_agent')
    can_delete = False


class CustomUserAdmin(BaseUserAdmin):
    inlines = [UserCourseInline, UserConsentInline]
    list_display = ('username', 'email', 'is_superuser', 'is_active', 'date_joined', 'last_login')
    list_filter = ('is_superuser', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('-date_joined',)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(UserCourse)
class UserCourseAdmin(admin.ModelAdmin):
    list_display = ('user', 'target_language', 'native_language',
                    'current_level', 'score', 'is_active', 'updated_at')
    list_filter = ('target_language', 'native_language', 'current_level', 'is_active')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('user',)


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    list_display = ('user', 'kind', 'accepted_at', 'ip_address')
    list_filter = ('kind',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('accepted_at',)
