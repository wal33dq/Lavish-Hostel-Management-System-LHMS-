from django import forms
import re
from django.db.models import Count
from .models import (
    Student, Room, Hostel, StudentFee,
    MessPlan, Expense, ExpenseCategory, FeeType, User
)

class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['name', 'contact_number', 'email', 'enrollment_date']
        widgets = {
            'enrollment_date': forms.DateInput(attrs={'type': 'date'}),
            'contact_number': forms.TextInput(attrs={'placeholder': 'e.g., +1234567890'}),
            'email': forms.EmailInput(attrs={'placeholder': 'student@example.com'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].required = True
        self.fields['contact_number'].required = False
        self.fields['email'].required = False

class RoomForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ['room_number', 'bed_type', 'number_of_beds']
        widgets = {
            'room_number': forms.TextInput(attrs={'placeholder': 'e.g., 101'}),
            'bed_type': forms.Select(choices=Room.BED_TYPE_CHOICES),
            'number_of_beds': forms.NumberInput(attrs={'min': 1, 'max': 3}),
        }

    def clean_number_of_beds(self):
        number_of_beds = self.cleaned_data['number_of_beds']
        bed_type = self.cleaned_data.get('bed_type')
        if bed_type:
            expected_beds = int(bed_type.split('-')[0])
            if number_of_beds != expected_beds:
                raise forms.ValidationError(f"Number of beds must be {expected_beds} for {bed_type} room.")
        return number_of_beds

class RoomAllocationForm(forms.Form):
    room = forms.ModelChoiceField(queryset=Room.objects.none(), empty_label="Select a room")

    def __init__(self, *args, hostel=None, **kwargs):
        super().__init__(*args, **kwargs)
        if hostel:
            available_rooms = Room.objects.filter(hostel=hostel).annotate(
                available_beds=Count('beds') - Count('beds__student')
            ).filter(available_beds__gt=0)
            self.fields['room'].queryset = available_rooms
            if not available_rooms.exists():
                self.fields['room'].empty_label = "No rooms available"

class StudentFeeForm(forms.ModelForm):
    fee_type = forms.ModelChoiceField(queryset=FeeType.objects.all())
    
    class Meta:
        model = StudentFee
        fields = ['fee_type', 'due_amount', 'paid_amount', 'period']
        widgets = {
            'due_amount': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'paid_amount': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'period': forms.TextInput(attrs={'placeholder': 'YYYY-MM'}),
        }

    def clean_paid_amount(self):
        paid_amount = self.cleaned_data['paid_amount']
        due_amount = self.cleaned_data.get('due_amount')
        if due_amount is not None and paid_amount > due_amount:
            raise forms.ValidationError("Paid amount cannot exceed due amount.")
        return paid_amount

    def clean_period(self):
        period = self.cleaned_data['period']
        fee_type = self.cleaned_data.get('fee_type')
        if fee_type and fee_type.periodicity == 'monthly' and not period:
            raise forms.ValidationError("Period (YYYY-MM) is required for monthly fees.")
        if period and not re.match(r'^\d{4}-\d{2}$', period):
            raise forms.ValidationError("Period must be in YYYY-MM format.")
        return period

class MessPlanForm(forms.ModelForm):
    class Meta:
        model = MessPlan
        fields = ['month', 'pdf_file']
        widgets = {
            'month': forms.TextInput(attrs={'placeholder': 'YYYY-MM'}),
            'pdf_file': forms.FileInput(),
        }

    def clean_month(self):
        month = self.cleaned_data['month']
        if not re.match(r'^\d{4}-\d{2}$', month):
            raise forms.ValidationError("Month must be in YYYY-MM format.")
        return month

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data['pdf_file']
        if pdf_file and not pdf_file.name.endswith('.pdf'):
            raise forms.ValidationError("File must be a PDF.")
        return pdf_file

class ExpenseForm(forms.ModelForm):
    category = forms.ModelChoiceField(queryset=ExpenseCategory.objects.all(), required=False)
    
    class Meta:
        model = Expense
        fields = ['category', 'description', 'amount', 'date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'amount': forms.NumberInput(attrs={'min': 0, 'step': '0.01'}),
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

class StudentUserForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    name = forms.CharField(max_length=100, required=True)
    contact_number = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'placeholder': 'e.g., +1234567890'}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'placeholder': 'student@example.com'}))
    enrollment_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    cnic = forms.CharField(max_length=15, required=True, widget=forms.TextInput(attrs={'placeholder': 'e.g., 12345-1234567-1'}))
    emergency_contact_number = forms.CharField(max_length=15, required=False, widget=forms.TextInput(attrs={'placeholder': 'e.g., +1234567890'}))

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_cnic(self):
        cnic = self.cleaned_data['cnic']
        if not re.match(r'^\d{5}-\d{7}-\d$', cnic):
            raise forms.ValidationError("CNIC must be in XXXXX-XXXXXXX-X format.")
        if Student.objects.filter(cnic=cnic).exists():
            raise forms.ValidationError("This CNIC is already registered.")
        return cnic

    def clean_emergency_contact_number(self):
        emergency_contact_number = self.cleaned_data['emergency_contact_number']
        if emergency_contact_number and not re.match(r'^\+\d{10,15}$', emergency_contact_number):
            raise forms.ValidationError("Emergency contact number must be in +XXXXXXXXXX format (10-15 digits).")
        return emergency_contact_number

class StudentCNICForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['cnic']
        widgets = {
            'cnic': forms.TextInput(attrs={'placeholder': 'e.g., 12345-1234567-1'}),
        }

    def clean_cnic(self):
        cnic = self.cleaned_data['cnic']
        if cnic and not re.match(r'^\d{5}-\d{7}-\d$', cnic):
            raise forms.ValidationError("CNIC must be in XXXXX-XXXXXXX-X format.")
        if cnic and Student.objects.exclude(id=self.instance.id).filter(cnic=cnic).exists():
            raise forms.ValidationError("This CNIC is already registered.")
        return cnic

class StudentEmergencyContactForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['emergency_contact_number']
        widgets = {
            'emergency_contact_number': forms.TextInput(attrs={'placeholder': 'e.g., +1234567890'}),
        }

    def clean_emergency_contact_number(self):
        emergency_contact_number = self.cleaned_data['emergency_contact_number']
        if emergency_contact_number and not re.match(r'^\+\d{10,15}$', emergency_contact_number):
            raise forms.ValidationError("Emergency contact number must be in +XXXXXXXXXX format (10-15 digits).")
        return emergency_contact_number

class WardenUserForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    hostel = forms.ModelChoiceField(queryset=Hostel.objects.all(), required=True, empty_label="Select a hostel")

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username