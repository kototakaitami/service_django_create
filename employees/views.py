from datetime import date as date_cls, datetime, timedelta

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from dashboard.models import ServicePlan
from diary.models import Entry

from .forms import AssignmentForm, EmployeeForm, ShiftPatternForm
from .models import Assignment, Attendance, Employee, ShiftPattern


# 従業員一覧
def employee_list(request):
    employees = Employee.objects.filter(is_superuser=False).order_by('-is_active', 'username')
    return render(request, 'employees/employee_list.html', {'employees': employees})


def employee_create(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('employees:employee_list')
    else:
        form = EmployeeForm()
    return render(request, 'employees/employee_form.html', {'form': form, 'title': '従業員の新規登録'})


def employee_update(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            return redirect('employees:employee_list')
    else:
        form = EmployeeForm(instance=employee)
    return render(request, 'employees/employee_form.html', {'form': form, 'title': '従業員情報の更新'})


def employee_delete(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    if request.method == 'POST':
        employee.delete()
        return redirect('employees:employee_list')
    return render(request, 'employees/employee_delete.html', {'employee': employee})


# 担当スケジュール（日付ごとの従業員×利用者の割当て）
def assignment_list(request):
    target_date = _parse_date(request.GET.get('date')) or timezone.localdate()
    assignments = (
        Assignment.objects.filter(date=target_date)
        .select_related('employee', 'user')
        .order_by('employee__username')
    )
    return render(request, 'employees/assignment_list.html', {
        'assignments': assignments,
        'target_date': target_date,
    })


def assignment_create(request):
    initial_date = _parse_date(request.GET.get('date')) or timezone.localdate()
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save()
            return redirect(f"{_assignment_list_url()}?date={assignment.date.isoformat()}")
    else:
        form = AssignmentForm(initial={'date': initial_date})
    return render(request, 'employees/assignment_form.html', {'form': form, 'title': '担当スケジュールの登録'})


def assignment_delete(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    if request.method == 'POST':
        target_date = assignment.date
        assignment.delete()
        return redirect(f"{_assignment_list_url()}?date={target_date.isoformat()}")
    return render(request, 'employees/assignment_delete.html', {'assignment': assignment})


# 出退勤記録（Slackボタンからの打刻を閲覧する画面）
def attendance_list(request):
    target_date = _parse_date(request.GET.get('date')) or timezone.localdate()
    records = (
        Attendance.objects.filter(date=target_date)
        .select_related('employee')
        .order_by('employee__username', 'kind')
    )
    return render(request, 'employees/attendance_list.html', {
        'records': records,
        'target_date': target_date,
    })


# カレンダー（利用者=終日イベント、スタッフ担当=時間帯イベント）
def calendar_view(request):
    today = timezone.localdate()
    return render(request, 'employees/calendar.html', {
        'this_year': today.year,
        'this_month': today.month,
    })


def calendar_events(request):
    '''FullCalendar用のイベントJSON。start/endはISO形式で渡される'''
    start = _parse_date((request.GET.get('start') or '')[:10])
    end = _parse_date((request.GET.get('end') or '')[:10])
    if not start or not end:
        return JsonResponse([], safe=False)

    events = []

    # 利用者の来所予定（サービス提供票の予定から終日イベントで表示）
    months = _months_between(start, end)
    plans = ServicePlan.objects.none()
    for year, month in months:
        plans = plans | ServicePlan.objects.filter(year=year, month=month)
    for plan in plans.select_related('user'):
        for day_str, value in (plan.schedule_json or {}).items():
            if value != '1':
                continue
            try:
                target = date_cls(plan.year, plan.month, int(day_str))
            except ValueError:
                continue
            if not (start <= target < end):
                continue
            events.append({
                'title': f'{plan.start_time:%H:%M}〜{plan.end_time:%H:%M} {plan.user.name}',
                'start': target.isoformat(),
                'allDay': True,
                'color': '#5b7c99',
            })

    # スタッフの担当（時間帯イベントで表示）
    assignments = (
        Assignment.objects.filter(date__gte=start, date__lt=end)
        .select_related('employee', 'user')
    )
    for a in assignments:
        title = f'{a.user.name}担当：{a.employee}'
        if a.is_daily_reporter:
            title += '（日報）'
        event = {'title': title, 'color': '#3a8a5f'}
        if a.start_time and a.end_time:
            event['start'] = datetime.combine(a.date, a.start_time).isoformat()
            event['end'] = datetime.combine(a.date, a.end_time).isoformat()
        else:
            event['start'] = a.date.isoformat()
            event['allDay'] = True
        events.append(event)

    return JsonResponse(events, safe=False)


@require_POST
def shift_generate(request):
    '''シフトパターンを指定月のAssignmentに一括展開する'''
    try:
        year = int(request.POST.get('year'))
        month = int(request.POST.get('month'))
    except (TypeError, ValueError):
        messages.error(request, '対象の年月が不正です')
        return redirect('employees:calendar')
    created = ShiftPattern.generate_assignments(year, month)
    messages.success(request, f'{year}年{month}月のシフトを生成しました（新規 {created} 件）')
    return redirect('employees:calendar')


# シフトパターン（いつも通りのシフトの型）
def pattern_list(request):
    patterns = ShiftPattern.objects.select_related('employee', 'user').all()
    return render(request, 'employees/pattern_list.html', {'patterns': patterns})


def pattern_create(request):
    if request.method == 'POST':
        form = ShiftPatternForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('employees:pattern_list')
    else:
        form = ShiftPatternForm()
    return render(request, 'employees/pattern_form.html', {'form': form, 'title': 'シフトパターンの登録'})


def pattern_update(request, pattern_id):
    pattern = get_object_or_404(ShiftPattern, id=pattern_id)
    if request.method == 'POST':
        form = ShiftPatternForm(request.POST, instance=pattern)
        if form.is_valid():
            form.save()
            return redirect('employees:pattern_list')
    else:
        form = ShiftPatternForm(instance=pattern)
    return render(request, 'employees/pattern_form.html', {'form': form, 'title': 'シフトパターンの更新'})


def pattern_delete(request, pattern_id):
    pattern = get_object_or_404(ShiftPattern, id=pattern_id)
    if request.method == 'POST':
        pattern.delete()
        return redirect('employees:pattern_list')
    return render(request, 'employees/pattern_delete.html', {'pattern': pattern})


# 日報の未提出一覧（日報担当なのにその日のEntryが無いもの）
def unsubmitted_reports(request):
    today = timezone.localdate()
    start = _parse_date(request.GET.get('from')) or today.replace(day=1)
    end = _parse_date(request.GET.get('to')) or today
    targets = (
        Assignment.objects.filter(
            is_daily_reporter=True, date__gte=start, date__lte=end,
        )
        .select_related('employee', 'user')
        .order_by('date', 'employee_id')
    )
    unsubmitted = [
        a for a in targets
        if not Entry.objects.filter(user=a.user, date=a.date).exists()
    ]
    return render(request, 'employees/unsubmitted_list.html', {
        'unsubmitted': unsubmitted,
        'from_date': start,
        'to_date': end,
    })


def _parse_date(value):
    if not value:
        return None
    try:
        return date_cls.fromisoformat(value)
    except ValueError:
        return None


def _months_between(start, end):
    '''startからendまでに含まれる (year, month) の一覧'''
    months = []
    cursor = start.replace(day=1)
    while cursor < end:
        months.append((cursor.year, cursor.month))
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return months


def _assignment_list_url():
    from django.urls import reverse
    return reverse('employees:assignment_list')
