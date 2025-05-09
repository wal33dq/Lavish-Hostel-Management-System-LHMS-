from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Hostel, Room, Bed, Student, FeeType, StudentFee, Expense, MessPlan

class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'hostel', 'is_staff')
    list_filter = ('role', 'is_staff', 'hostel')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Role Info', {'fields': ('role', 'hostel', 'student')}),
    )

@admin.register(Hostel)
class HostelAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'owner', 'total_funds')
    list_filter = ('owner',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'hostel', 'bed_type', 'number_of_beds')
    list_filter = ('hostel', 'bed_type')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('name', 'hostel', 'room', 'bed')
    search_fields = ('name', 'contact_number')

@admin.register(StudentFee)
class StudentFeeAdmin(admin.ModelAdmin):
    list_display = ('student', 'fee_type', 'period', 'due_amount', 'paid_amount')
    list_filter = ('fee_type', 'period')

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('hostel', 'category', 'amount', 'date')
    list_filter = ('category', 'date')

@admin.register(MessPlan)
class MessPlanAdmin(admin.ModelAdmin):
    list_display = ('hostel', 'month', 'pdf_file')
    list_filter = ('hostel',)

@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ('bed_number', 'room', 'student')
    list_filter = ('room',)

@admin.register(FeeType)
class FeeTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'periodicity')

admin.site.register(User, UserAdmin)