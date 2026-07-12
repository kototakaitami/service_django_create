from django.urls import path

from . import views

app_name = 'employees'
urlpatterns = [
    path('', views.employee_list, name='employee_list'),
    path('create/', views.employee_create, name='employee_create'),
    path('<int:employee_id>/edit/', views.employee_update, name='employee_update'),
    path('<int:employee_id>/delete/', views.employee_delete, name='employee_delete'),

    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/create/', views.assignment_create, name='assignment_create'),
    path('assignments/<int:assignment_id>/delete/', views.assignment_delete, name='assignment_delete'),

    path('attendances/', views.attendance_list, name='attendance_list'),

    path('calendar/', views.calendar_view, name='calendar'),
    path('api/calendar-events/', views.calendar_events, name='calendar_events'),
    path('shift-generate/', views.shift_generate, name='shift_generate'),

    path('patterns/', views.pattern_list, name='pattern_list'),
    path('patterns/create/', views.pattern_create, name='pattern_create'),
    path('patterns/<int:pattern_id>/edit/', views.pattern_update, name='pattern_update'),
    path('patterns/<int:pattern_id>/delete/', views.pattern_delete, name='pattern_delete'),

    path('reports/unsubmitted/', views.unsubmitted_reports, name='unsubmitted_reports'),
]
