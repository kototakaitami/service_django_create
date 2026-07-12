from django import forms
from django.forms.utils import ErrorList

from .models import Assignment, Employee, ShiftPattern


class EmployeeForm(forms.ModelForm):
    required_css_class = 'required'

    password = forms.CharField(
        label='パスワード', required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='ログイン機能導入時に使用。空欄の場合は変更されません（新規時はログイン不可のまま作成）',
    )

    class Meta:
        model = Employee
        fields = ['username', 'last_name', 'first_name', 'name_kana',
                  'email', 'tel', 'slack_user_id', 'is_active']
        labels = {
            'username': 'ログインID',
            'last_name': '姓',
            'first_name': '名',
            'email': 'メールアドレス',
            'is_active': '在籍中',
        }

    def clean(self):
        cleaned = super().clean()
        slack_user_id = (cleaned.get('slack_user_id') or '').strip()
        if slack_user_id and not slack_user_id.startswith('U'):
            self._errors['slack_user_id'] = ErrorList(
                ['SlackユーザーIDは「U」で始まるメンバーIDを入力してください']
            )
        cleaned['slack_user_id'] = slack_user_id
        return cleaned

    def save(self, commit=True):
        employee = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            employee.set_password(password)
        elif not employee.pk:
            employee.set_unusable_password()
        if commit:
            employee.save()
        return employee

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            self.fields[field_name].widget.attrs['class'] = f'form-control {field_name}'
            if field.required:
                self.fields[field_name].widget.attrs['required'] = True
                self.fields[field_name].widget.attrs['class'] = f'form-control {field_name} required'


class AssignmentForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = Assignment
        fields = ['date', 'employee', 'user', 'start_time', 'end_time',
                  'is_daily_reporter', 'note']
        labels = {
            'date': '日付',
            'employee': '従業員',
            'user': '利用者',
            'note': 'メモ',
        }
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get('employee')
        user = cleaned.get('user')
        date = cleaned.get('date')
        if employee and user and date:
            queryset = Assignment.objects.filter(employee=employee, user=user, date=date)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                self._errors['user'] = ErrorList(['同じ日付・従業員・利用者の割当てが既に登録されています'])
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True)
        for field_name, field in self.fields.items():
            self.fields[field_name].widget.attrs['class'] = f'form-control {field_name}'
            if field.required:
                self.fields[field_name].widget.attrs['required'] = True
                self.fields[field_name].widget.attrs['class'] = f'form-control {field_name} required'


class ShiftPatternForm(forms.ModelForm):
    required_css_class = 'required'

    class Meta:
        model = ShiftPattern
        fields = ['weekday', 'employee', 'user', 'start_time', 'end_time',
                  'is_daily_reporter', 'is_active']
        labels = {
            'employee': '従業員',
            'user': '利用者',
        }
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get('employee')
        user = cleaned.get('user')
        weekday = cleaned.get('weekday')
        if employee and user and weekday is not None:
            queryset = ShiftPattern.objects.filter(employee=employee, user=user, weekday=weekday)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                self._errors['weekday'] = ErrorList(['同じ曜日・従業員・利用者のパターンが既に登録されています'])
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True)
        for field_name, field in self.fields.items():
            self.fields[field_name].widget.attrs['class'] = f'form-control {field_name}'
            if field.required:
                self.fields[field_name].widget.attrs['required'] = True
                self.fields[field_name].widget.attrs['class'] = f'form-control {field_name} required'
