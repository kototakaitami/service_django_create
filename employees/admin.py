from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Assignment, Attendance, Employee, ShiftPattern


@admin.register(Employee)
class EmployeeAdmin(UserAdmin):
    list_display = ['username', 'last_name', 'first_name', 'slack_user_id', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('従業員情報', {'fields': ('name_kana', 'tel', 'slack_user_id')}),
    )


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['date', 'employee', 'user', 'start_time', 'end_time', 'is_daily_reporter']
    list_filter = ['date', 'employee', 'is_daily_reporter']


@admin.register(ShiftPattern)
class ShiftPatternAdmin(admin.ModelAdmin):
    list_display = ['weekday', 'employee', 'user', 'start_time', 'end_time',
                    'is_daily_reporter', 'is_active']
    list_filter = ['weekday', 'is_active']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['date', 'employee', 'kind', 'timestamp']
    list_filter = ['date', 'kind']
