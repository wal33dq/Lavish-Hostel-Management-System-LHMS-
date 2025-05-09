from django.urls import path
from core import views

urlpatterns = [
  path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('warden/dashboard/', views.warden_dashboard, name='warden_dashboard'),
    path('owner/dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('warden/register_student/', views.register_student, name='register_student'),
    path('warden/create_room/', views.create_room, name='create_room'),
    path('warden/allocate_room/<int:student_id>/', views.allocate_room, name='allocate_room'),
    path('warden/manage_fees/<int:student_id>/', views.manage_fees, name='manage_fees'),
    path('warden/upload_mess_plan/', views.upload_mess_plan, name='upload_mess_plan'),
    path('warden/add_expense/', views.add_expense, name='add_expense'),
    path('warden/manage_categories/', views.manage_categories, name='manage_categories'),
    path('warden/create_student_user/', views.create_student_user, name='create_student_user'),
    path('warden/update_student_cnic/<int:student_id>/', views.update_student_cnic, name='update_student_cnic'),
    path('warden/update_student_emergency_contact/<int:student_id>/', views.update_student_emergency_contact, name='update_student_emergency_contact'),
]