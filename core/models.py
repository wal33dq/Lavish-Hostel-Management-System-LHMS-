from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from decimal import Decimal

class FeeType(models.Model):
    name = models.CharField(max_length=100)
    periodicity = models.CharField(max_length=20, choices=(
        ('monthly', 'Monthly'), 
        ('one-time', 'One-time')
    ))

    def __str__(self):
        return self.name

class Hostel(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    owner = models.ForeignKey('User', on_delete=models.CASCADE, related_name='owned_hostels')
    total_funds = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def update_funds(self, amount, is_expense=False):
        if is_expense:
            self.total_funds -= Decimal(amount)
        else:
            self.total_funds += Decimal(amount)
        self.save()
    
    def __str__(self):
        return self.name

class Room(models.Model):
    BED_TYPE_CHOICES = (
        ('1-bed', 'Single Bed'),
        ('2-bed', 'Double Bed'),
        ('3-bed', 'Triple Bed'),
    )
    
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='rooms')
    room_number = models.CharField(max_length=10)
    bed_type = models.CharField(max_length=10, choices=BED_TYPE_CHOICES)
    number_of_beds = models.PositiveIntegerField()

    class Meta:
        unique_together = ('hostel', 'room_number')

    def available_beds(self):
        return self.beds.filter(student__isnull=True).count()

    def __str__(self):
        return f"{self.room_number} ({self.get_bed_type_display()})"

class Bed(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='beds')
    bed_number = models.CharField(max_length=10)
    student = models.OneToOneField('Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_bed')

    def __str__(self):
        return f"Bed {self.bed_number} in {self.room}"

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    ROLE_CHOICES = (
        ('Student', 'Student'),
        ('Warden', 'Warden'),
        ('Owner', 'Owner'),
        ('Admin', 'Admin'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    student = models.OneToOneField('Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='user_account')
    hostel = models.ForeignKey(Hostel, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff')

    def __str__(self):
        return self.username

class Student(models.Model):
    name = models.CharField(max_length=100)
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='students')
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='occupants')
    bed = models.OneToOneField(Bed, on_delete=models.SET_NULL, null=True, blank=True, related_name='occupant')
    contact_number = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    enrollment_date = models.DateField(default=timezone.now)
    cnic = models.CharField(max_length=15, blank=True, unique=True, verbose_name="CNIC")
    emergency_contact_number = models.CharField(max_length=15, blank=True, verbose_name="Emergency Contact Number")

    def fee_status(self):
        return {
            'security': self.fees.filter(fee_type__name='security').first(),
            'seat': self.fees.filter(fee_type__name='seat').first(),
            'mess': self.fees.filter(fee_type__name='mess').first()
        }

    def __str__(self):
        return self.name

class StudentFee(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fees')
    fee_type = models.ForeignKey(FeeType, on_delete=models.CASCADE)
    period = models.CharField(max_length=7, blank=True, null=True)
    due_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.pk:  # Update existing fee
            old_fee = StudentFee.objects.get(pk=self.pk)
            difference = self.paid_amount - old_fee.paid_amount
            self.student.hostel.update_funds(difference)
        else:  # New fee
            self.student.hostel.update_funds(self.paid_amount)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.fee_type} for {self.student} ({self.period})"

class Expense(models.Model):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='expenses')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.hostel.update_funds(self.amount, is_expense=True)

    def __str__(self):
        return f"{self.description} ({self.hostel.name}) on {self.date}"

class MessPlan(models.Model):
    hostel = models.ForeignKey(Hostel, on_delete=models.CASCADE, related_name='mess_plans')
    month = models.CharField(max_length=7)
    pdf_file = models.FileField(upload_to='mess_plans/')

    def __str__(self):
        return f"Mess Plan for {self.hostel} ({self.month})"