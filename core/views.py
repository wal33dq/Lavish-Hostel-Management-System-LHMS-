from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.db.models import Sum, F, Count
from .models import *
from .forms import *
from functools import wraps

def role_required(role):
    @wraps(role_required)
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("You must be logged in to access this page.")
            if request.user.is_superuser or request.user.role == role:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("You do not have permission to access this page.")
        return wrapper
    return decorator

def login_view(request):
    if request.user.is_authenticated:
        if request.user.role == 'Student':
            return redirect('student_dashboard')
        elif request.user.role == 'Warden':
            return redirect('warden_dashboard')
        elif request.user.role == 'Owner' or request.user.is_superuser:
            return redirect('owner_dashboard')
        elif request.user.role == 'Admin':
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid role. Please contact the administrator.")
            return redirect('logout')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome, {user.username}!")
            if user.role == 'Student':
                return redirect('student_dashboard')
            elif user.role == 'Warden':
                return redirect('warden_dashboard')
            elif user.role == 'Owner' or user.is_superuser:
                return redirect('owner_dashboard')
            elif user.role == 'Admin':
                return redirect('admin_dashboard')
            else:
                messages.error(request, "Invalid role. Please contact the administrator.")
                return redirect('logout')
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'login.html', {})


def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')

@role_required('Student')
def student_dashboard(request):
    student = request.user.student
    fees = StudentFee.objects.filter(student=student)
    mess_plan = MessPlan.objects.filter(
        hostel=student.hostel,
        month=timezone.now().strftime('%Y-%m')
    ).first()
    context = {
        'user': request.user,
        'student': student,
        'fees': fees,
        'mess_plan': mess_plan,
    }
    return render(request, 'student_dashboard.html', context)

@role_required('Warden')
def warden_dashboard(request):
    hostel = request.user.hostel
    if not hostel:
        messages.error(request, "No hostel is linked to this warden. Please contact the admin.")
        return redirect('logout')

    students = Student.objects.filter(hostel=hostel).prefetch_related('room', 'bed', 'fees')
    fees = StudentFee.objects.filter(student__hostel=hostel)
    expenses = Expense.objects.filter(hostel=hostel)

    fees_summary = {}
    for student in students:
        student_fees = fees.filter(student=student)
        fees_summary[student.id] = {}
        for fee in student_fees:
            fees_summary[student.id][fee.fee_type.name.lower()] = fee

    total_fees = fees.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
    total_expenses = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    current_funds = total_fees - total_expenses

    recent_expenses = expenses.order_by('-date')[:5]
    mess_plan = MessPlan.objects.filter(
        hostel=hostel,
        month=timezone.now().strftime('%Y-%m')
    ).first()

    context = {
        'user': request.user,
        'hostel': hostel,
        'students': students,
        'fees_summary': fees_summary,
        'total_fees': total_fees,
        'total_expenses': total_expenses,
        'current_funds': current_funds,
        'recent_expenses': recent_expenses,
        'mess_plan': mess_plan,
    }
    return render(request, 'warden_dashboard.html', context)

@role_required('Owner')
def owner_dashboard(request):
    try:
        hostels = Hostel.objects.filter(owner=request.user)
        if not hostels:
            messages.warning(request, "No hostels are assigned to this owner.")
            return render(request, 'owner_dashboard.html', {
                'user': request.user,
                'error': "No hostels owned by this user.",
                'warden_form': WardenUserForm()  # Ensure form is available even if no hostels
            })

        # Seat availability across all hostels
        seat_availability = []
        for hostel in hostels:
            rooms = Room.objects.filter(hostel=hostel)
            for room in rooms:
                total_beds = room.number_of_beds
                occupied = room.occupants.count()
                available = total_beds - occupied
                seat_availability.append({
                    'hostel': hostel.name,
                    'room': room.room_number,
                    'total_beds': total_beds,
                    'occupied': occupied,
                    'available': available
                })

        # Unpaid students and pending fee status
        unpaid_students = []
        for hostel in hostels:
            students = Student.objects.filter(hostel=hostel).prefetch_related('fees')
            for student in students:
                fees = student.fees.all()
                pending = fees.filter(paid_amount__lt=F('due_amount')).aggregate(total_pending=Sum('due_amount') - Sum('paid_amount'))['total_pending'] or 0
                if pending > 0:
                    unpaid_students.append({
                        'student': student.name,
                        'hostel': hostel.name,
                        'pending_amount': pending
                    })

        # Expenses by category
        expenses_by_category = Expense.objects.filter(hostel__in=hostels).values('category__name').annotate(total=Sum('amount')).order_by('category__name')

        # Security fee totals
        security_fees = StudentFee.objects.filter(student__hostel__in=hostels, fee_type__name__iexact='security').aggregate(total_security=Sum('paid_amount'))['total_security'] or 0

        # Total revenue
        total_fees_collected = StudentFee.objects.filter(student__hostel__in=hostels).aggregate(total=Sum('paid_amount'))['total'] or 0
        total_expenses = Expense.objects.filter(hostel__in=hostels).aggregate(total=Sum('amount'))['total'] or 0
        total_revenue = total_fees_collected - total_expenses

        # Hostel revenue report
        hostel_revenue = []
        for hostel in hostels:
            hostel_fees = StudentFee.objects.filter(student__hostel=hostel).aggregate(total=Sum('paid_amount'))['total'] or 0
            hostel_expenses = Expense.objects.filter(hostel=hostel).aggregate(total=Sum('amount'))['total'] or 0
            hostel_revenue.append({
                'hostel': hostel.name,
                'fees_collected': hostel_fees,
                'expenses': hostel_expenses,
                'revenue': hostel_fees - hostel_expenses
            })

        # Initialize the form with filtered hostel choices
        form = WardenUserForm(initial={'hostel': hostels.first() if hostels else None})
        form.fields['hostel'].queryset = hostels  # Limit hostel choices to owner's hostels

        if request.method == 'POST':
            form = WardenUserForm(request.POST)
            if form.is_valid():
                try:
                    hostel = form.cleaned_data['hostel']
                    if hostel not in hostels:  # More explicit check
                        messages.error(request, "You can only assign wardens to your own hostels.")
                        return redirect('owner_dashboard')
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        password=form.cleaned_data['password'],
                        role='Warden',
                        hostel=hostel
                    )
                    messages.success(request, f"Warden user {user.username} created successfully")
                    return redirect('owner_dashboard')
                except Exception as e:
                    messages.error(request, f"Error creating warden user: {str(e)}")
            else:
                messages.error(request, "Form validation failed: " + str(form.errors))
        else:
            form = WardenUserForm()
            form.fields['hostel'].queryset = hostels

        context = {
            'user': request.user,
            'hostels': hostels,
            'students': Student.objects.filter(hostel__in=hostels),
            'fees': StudentFee.objects.filter(student__hostel__in=hostels),
            'expenses': Expense.objects.filter(hostel__in=hostels),
            'mess_plans': MessPlan.objects.filter(hostel__in=hostels, month=timezone.now().strftime('%Y-%m')),
            'seat_availability': seat_availability,
            'unpaid_students': unpaid_students,
            'expenses_by_category': expenses_by_category,
            'security_fees': security_fees,
            'total_revenue': total_revenue,
            'hostel_revenue': hostel_revenue,
            'warden_form': form,
        }
        return render(request, 'owner_dashboard.html', context)

    except Exception as e:
        messages.error(request, f"An error occurred while loading the dashboard: {str(e)}")
        return render(request, 'owner_dashboard.html', {
            'user': request.user,
            'error': f"An error occurred: {str(e)}",
            'warden_form': WardenUserForm()  # Provide a default form in case of error
        })

@role_required('Admin')
def admin_dashboard(request):
    context = {
        'user': request.user,
    }
    return render(request, 'admin_dashboard.html', context)

@role_required('Warden')
def register_student(request):
    if not request.user.hostel:
        messages.error(request, "No hostel is linked to this warden. Please contact the admin.")
        return redirect('warden_dashboard')

    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save(commit=False)
            student.hostel = request.user.hostel
            student.save()
            messages.success(request, f"Student {student.name} registered successfully")
            return redirect('warden_dashboard')
    else:
        form = StudentForm()
    return render(request, 'register_student.html', {'form': form})

@role_required('Warden')
def create_room(request):
    if not request.user.hostel:
        messages.error(request, "No hostel is linked to this warden. Please contact the admin.")
        return redirect('warden_dashboard')

    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.hostel = request.user.hostel
            room.save()
            for i in range(1, room.number_of_beds + 1):
                Bed.objects.create(room=room, bed_number=i)
            messages.success(request, f"Room {room.room_number} created successfully")
            return redirect('warden_dashboard')
    else:
        form = RoomForm()
    return render(request, 'create_room.html', {'form': form})

@role_required('Warden')
def allocate_room(request, student_id):
    student = get_object_or_404(Student, id=student_id, hostel=request.user.hostel)
    if request.method == 'POST':
        form = RoomAllocationForm(request.POST, hostel=request.user.hostel)
        if form.is_valid():
            room = form.cleaned_data['room']
            available_bed = Bed.objects.filter(room=room, student__isnull=True).first()
            if available_bed:
                if student.bed:
                    student.bed.student = None
                    student.bed.save()
                student.room = room
                student.bed = available_bed
                available_bed.student = student
                student.save()
                available_bed.save()
                messages.success(request, f"Room allocated to {student.name} successfully")
                return redirect('warden_dashboard')
            else:
                messages.error(request, "No available beds in the selected room.")
    else:
        form = RoomAllocationForm(hostel=request.user.hostel)
    return render(request, 'allocate_room.html', {'form': form, 'student': student})

@role_required('Warden')
def manage_fees(request, student_id):
    student = get_object_or_404(Student, id=student_id, hostel=request.user.hostel)
    if request.method == 'POST':
        form = StudentFeeForm(request.POST)
        if form.is_valid():
            fee = form.save(commit=False)
            fee.student = student
            fee.save()
            messages.success(request, f"Fee updated for {student.name}")
            return redirect('warden_dashboard')
    else:
        form = StudentFeeForm()
    existing_fees = StudentFee.objects.filter(student=student)
    return render(request, 'manage_fees.html', {
        'form': form,
        'student': student,
        'existing_fees': existing_fees
    })

@role_required('Warden')
def upload_mess_plan(request):
    if not request.user.hostel:
        messages.error(request, "No hostel is linked to this warden. Please contact the admin.")
        return redirect('warden_dashboard')

    if request.method == 'POST':
        form = MessPlanForm(request.POST, request.FILES)
        if form.is_valid():
            mess_plan = form.save(commit=False)
            mess_plan.hostel = request.user.hostel
            mess_plan.save()
            messages.success(request, "Mess plan uploaded successfully")
            return redirect('warden_dashboard')
    else:
        form = MessPlanForm()
    return render(request, 'upload_mess_plan.html', {'form': form})

@role_required('Warden')
def add_expense(request):
    if not request.user.hostel:
        messages.error(request, "No hostel is linked to this warden. Please contact the admin.")
        return redirect('warden_dashboard')

    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.hostel = request.user.hostel
            expense.save()
            messages.success(request, "Expense added successfully")
            return redirect('warden_dashboard')
    else:
        form = ExpenseForm()
    return render(request, 'add_expense.html', {'form': form})

@role_required('Warden')
def manage_categories(request):
    if request.method == 'POST':
        name = request.POST.get('category_name')
        if name:
            ExpenseCategory.objects.get_or_create(name=name)
            messages.success(request, f"Category '{name}' added successfully")
            return redirect('manage_categories')
    categories = ExpenseCategory.objects.all()
    return render(request, 'manage_categories.html', {'categories': categories})

@role_required('Warden')
def create_student_user(request):
    if not request.user.hostel:
        messages.error(request, "No hostel is linked to this warden. Please contact the admin.")
        return redirect('warden_dashboard')

    if request.method == 'POST':
        form = StudentUserForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    role='Student'
                )
                student = Student.objects.create(
                    name=form.cleaned_data['name'],
                    contact_number=form.cleaned_data['contact_number'],
                    email=form.cleaned_data['email'],
                    enrollment_date=form.cleaned_data['enrollment_date'],
                    cnic=form.cleaned_data['cnic'],
                    emergency_contact_number=form.cleaned_data['emergency_contact_number'],
                    hostel=request.user.hostel
                )
                user.student = student
                user.save()
                messages.success(request, f"Student user {user.username} created successfully")
                return redirect('warden_dashboard')
            except Exception as e:
                messages.error(request, f"Error creating student user: {str(e)}")
        else:
            messages.error(request, "Form validation failed. Please check the errors below.")
    else:
        form = StudentUserForm()
    return render(request, 'create_student_user.html', {'form': form})

@role_required('Warden')
def update_student_cnic(request, student_id):
    student = get_object_or_404(Student, id=student_id, hostel=request.user.hostel)
    if request.method == 'POST':
        form = StudentCNICForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, f"CNIC updated for {student.name}")
            return redirect('warden_dashboard')
    else:
        form = StudentCNICForm(instance=student)
    return render(request, 'update_student_cnic.html', {'form': form, 'student': student})

@role_required('Warden')
def update_student_emergency_contact(request, student_id):
    student = get_object_or_404(Student, id=student_id, hostel=request.user.hostel)
    if request.method == 'POST':
        form = StudentEmergencyContactForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, f"Emergency contact updated for {student.name}")
            return redirect('warden_dashboard')
    else:
        form = StudentEmergencyContactForm(instance=student)
    return render(request, 'update_student_emergency_contact.html', {'form': form, 'student': student})