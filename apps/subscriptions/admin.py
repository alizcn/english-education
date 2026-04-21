from django.contrib import admin

from .models import Plan, Subscription, Payment, TrialUsage


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'price_try', 'duration_days', 'is_popular', 'is_active', 'sort_order')
    list_editable = ('is_active', 'is_popular', 'sort_order')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'starts_at', 'expires_at', 'created_at')
    list_filter = ('status', 'plan')
    search_fields = ('user__username',)
    autocomplete_fields = ('user', 'plan')
    date_hierarchy = 'created_at'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'amount', 'conversation_id', 'created_at')
    list_filter = ('status', 'plan')
    search_fields = ('user__username', 'conversation_id', 'iyzico_token')
    readonly_fields = ('conversation_id', 'iyzico_token', 'iyzico_payment_id',
                       'raw_init_response', 'raw_verify_response', 'created_at', 'updated_at')


@admin.register(TrialUsage)
class TrialUsageAdmin(admin.ModelAdmin):
    list_display = ('user', 'trial_started_at', 'trial_ends_at',
                    'interview_count', 'chat_count', 'bulk_translate_count')
    search_fields = ('user__username',)
    readonly_fields = ('trial_started_at',)
