from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (Activity, AuditEvent, Challenge, Enrollment, Goal, LedgerEntry, LedgerTransaction,
                     Notification, PointAccount, Redemption, Reward, Subscription, User, WalletLink)
from .services import review_activity

@admin.register(User)
class WellifyUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Wellify profile', {'fields': ('city', 'bio')}),)

class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Activity)
class ActivityAdmin(ReadOnlyAdmin):
    list_display = ['id', 'user', 'date', 'source', 'steps', 'status']
    list_filter = ['status', 'source', 'date']
    actions = ['approve', 'reject']
    @admin.action(description='Approve selected pending activity')
    def approve(self, request, queryset):
        for item in queryset:
            review_activity(item.pk, request.user, True)
    @admin.action(description='Reject selected pending activity')
    def reject(self, request, queryset):
        for item in queryset:
            review_activity(item.pk, request.user, False)

@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ['name', 'points_cost', 'stock', 'active']
    list_filter = ['active']

@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ['title', 'starts_on', 'ends_on', 'target_steps', 'points', 'active']

@admin.register(Redemption)
class RedemptionAdmin(ReadOnlyAdmin):
    list_display = ['id', 'user', 'reward', 'points_cost', 'status', 'created_at']

for model in [PointAccount, LedgerTransaction, LedgerEntry, AuditEvent, WalletLink, Enrollment]:
    admin.site.register(model, ReadOnlyAdmin)
for model in [Goal, Notification, Subscription]:
    admin.site.register(model)
admin.site.site_header = 'Wellify administration'
admin.site.site_title = 'Wellify admin'
