from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.db.models import Sum
from .models import *
from .forms import *
from functools import wraps
from django.db.models import Count

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if user.role == 'Student':
                return redirect('student_dashboard')
            elif user.role == 'Warden':
                return redirect('warden_dashboard')
            elif user.role == 'Owner':
                return redirect('owner_dashboard')
            elif user.role == 'Admin':
                return redirect('admin_dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.role != role:
                return HttpResponseForbidden("You do not have permission to access this page.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

@role_required('Student')
def student_dashboard(request):
    student = request.user.student
    if not student:
        return render(request, 'student_dashboard.html', {
            'user': request.user,
            'error': "No student profile linked to this user."
        })
    fees = StudentFee.objects.filter(student=student)
    current_month = timezone.now().strftime('%Y-%m')
    mess_plan = MessPlan.objects.filter(hostel=student.hostel, month=current_month).first() if student.hostel else None
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
        return render(request, 'warden_dashboard.html', {'error': "No hostel linked to this warden."})

    students = Student.objects.filter(hostel=hostel).select_related('room', 'bed').prefetch_related('fees')
    rooms = Room.objects.filter(hostel=hostel).prefetch_related('beds')
    total_fees = StudentFee.objects.filter(student__hostel=hostel).aggregate(total=Sum('paid_amount'))['total'] or 0
    total_expenses = Expense.objects.filter(hostel=hostel).aggregate(total=Sum('amount'))['total'] or 0

    fees_summary = {}
    for student in students:
        fees_summary[student.id] = {
            'security': student.fees.filter(fee_type__name__iexact='security').first(),
            'seat': student.fees.filter(fee_type__name__iexact='seat').first(),
            'mess': student.fees.filter(fee_type__name__iexact='mess').first(),
        }

    context = {
        'user': request.user,
        'hostel': hostel,
        'students': students,
        'rooms': rooms,
        'total_fees': total_fees,
        'total_expenses': total_expenses,
        'current_funds': hostel.total_funds,
        'recent_expenses': Expense.objects.filter(hostel=hostel).order_by('-date')[:5],
        'fees_summary': fees_summary,
        'mess_plan': MessPlan.objects.filter(hostel=hostel, month=timezone.now().strftime('%Y-%m')).first(),
    }
    return render(request, 'warden_dashboard.html', context)

@role_required('Warden')
def register_student(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            student = form.save(commit=False)
            student.hostel = request.user.hostel
            student.save()
            messages.success(request, 'Student registered successfully')
            return redirect('warden_dashboard')
    else:
        form = StudentForm()
    return render(request, 'register_student.html', {'form': form})

@role_required('Warden')
def create_room(request):
    if request.method == 'POST':
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.hostel = request.user.hostel
            room.save()
            for i in range(1, room.number_of_beds + 1):
                Bed.objects.create(
                    room=room,
                    bed_number=f"{room.room_number}-{i}",
                )
            messages.success(request, f'Room {room.room_number} created with {room.number_of_beds} beds')
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
            bed = room.beds.filter(student__isnull=True).first()
            if bed:
                if student.bed:
                    old_bed = student.bed
                    old_bed.student = None
                    old_bed.save()
                bed.student = student
                bed.save()
                student.room = room
                student.bed = bed
                student.save()
                messages.success(request, f'Allocated {room.room_number} - Bed {bed.bed_number} to {student.name}')
                return redirect('warden_dashboard')
            else:
                form.add_error('room', "No available beds in selected room")
    else:
        form = RoomAllocationForm(hostel=request.user.hostel)
    return render(request, 'allocate_room.html', {
        'form': form,
        'student': student,
        'available_rooms': Room.objects.filter(hostel=request.user.hostel)
                                     .annotate(available_beds=Count('beds') - Count('beds__student'))
    })

@role_required('Warden')
def manage_fees(request, student_id):
    student = get_object_or_404(Student, id=student_id, hostel=request.user.hostel)
    fees = student.fees.all()
    if request.method == 'POST':
        form = StudentFeeForm(request.POST)
        if form.is_valid():
            fee = form.save(commit=False)
            fee.student = student
            fee.save()
            messages.success(request, 'Fee record updated successfully')
            return redirect('manage_fees', student_id=student_id)
    else:
        form = StudentFeeForm(initial={'student': student})
    return render(request, 'manage_fees.html', {
        'student': student,
        'fees': fees,
        'form': form,
        'total_paid': fees.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
    })

@role_required('Warden')
def upload_mess_plan(request):
    if request.method == 'POST':
        form = MessPlanForm(request.POST, request.FILES)
        if form.is_valid():
            mess_plan = form.save(commit=False)
            mess_plan.hostel = request.user.hostel
            mess_plan.save()
            messages.success(request, 'Mess plan uploaded successfully')
            return redirect('warden_dashboard')
    else:
        form = MessPlanForm()
    return render(request, 'upload_mess_plan.html', {'form': form})

@role_required('Warden')
def add_expense(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.hostel = request.user.hostel
            expense.save()
            messages.success(request, 'Expense recorded successfully')
            return redirect('warden_dashboard')
    else:
        form = ExpenseForm()
    return render(request, 'add_expense.html', {'form': form})

@role_required('Warden')
def manage_categories(request):
    categories = ExpenseCategory.objects.all()
    if request.method == 'POST':
        name = request.POST.get('name')
        if name:
            ExpenseCategory.objects.create(name=name)
            messages.success(request, 'Category added successfully')
            return redirect('manage_categories')
    return render(request, 'manage_categories.html', {'categories': categories})

@role_required('Owner')
def owner_dashboard(request):
    hostels = Hostel.objects.filter(owner=request.user)
    if not hostels:
        return render(request, 'owner_dashboard.html', {
            'user': request.user,
            'error': "No hostels owned by this user."
        })
    students = Student.objects.filter(hostel__in=hostels)
    fees = StudentFee.objects.filter(student__hostel__in=hostels)
    expenses = Expense.objects.filter(hostel__in=hostels)
    current_month = timezone.now().strftime('%Y-%m')
    mess_plans = MessPlan.objects.filter(hostel__in=hostels, month=current_month)
    context = {
        'user': request.user,
        'hostels': hostels,
        'students': students,
        'fees': fees,
        'expenses': expenses,
        'mess_plans': mess_plans,
    }
    return render(request, 'owner_dashboard.html', context)

@role_required('Admin')
def admin_dashboard(request):
    hostels = Hostel.objects.all()
    students = Student.objects.all()
    fees = StudentFee.objects.all()
    expenses = Expense.objects.all()
    current_month = timezone.now().strftime('%Y-%m')
    mess_plans = MessPlan.objects.filter(month=current_month)
    context = {
        'user': request.user,
        'hostels': hostels,
        'students': students,
        'fees': fees,
        'expenses': expenses,
        'mess_plans': mess_plans,
    }
    return render(request, 'admin_dashboard.html', context)

def handler400(request, exception):
    return render(request, '400.html', status=400)

def handler403(request, exception):
    return render(request, '403.html', status=403)

def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler500(request):
    return render(request, '500.html', status=500)