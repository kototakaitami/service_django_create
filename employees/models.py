import calendar as calendar_module
from datetime import date as date_cls

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class Employee(AbstractUser):
    '''従業員（ログインユーザー）

    AUTH_USER_MODEL として使用する。dashboard.User（被保険者/利用者）とは別物なので注意。
    Slack連携: slack_user_id にSlackのメンバーID（U...）を設定すると
    出退勤ボタン・日報プロンプトの送信対象になる。
    '''
    slack_user_id = models.CharField(
        'SlackユーザーID', max_length=20, blank=True, default='',
        help_text='Slackプロフィール →「…」→「メンバーIDをコピー」で取得（例: U0A1E588J2J）',
    )
    name_kana = models.CharField('フリガナ', max_length=100, blank=True, default='')
    tel = models.CharField('電話番号', max_length=20, blank=True, default='')

    class Meta:
        verbose_name = '従業員'
        verbose_name_plural = '従業員'

    def __str__(self):
        # 日本式の「姓 名」で表示する（get_full_name は名→姓の欧米式のため使わない）
        full_name = f'{self.last_name} {self.first_name}'.strip()
        return full_name if full_name else self.username


WEEKDAY_CHOICES = [
    (0, '月'), (1, '火'), (2, '水'), (3, '木'), (4, '金'), (5, '土'), (6, '日'),
]


class Assignment(models.Model):
    '''勤怠スケジュール: その日、どの従業員がどの利用者を担当するか

    通常は ShiftPattern から月単位で一括生成し、例外の日だけ個別に編集する。
    '''
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        verbose_name='従業員', related_name='assignments',
    )
    user = models.ForeignKey(
        'dashboard.User', on_delete=models.CASCADE,
        verbose_name='利用者', related_name='assignments',
    )
    date = models.DateField('日付')
    start_time = models.TimeField('開始時刻', null=True, blank=True)
    end_time = models.TimeField('終了時刻', null=True, blank=True)
    is_daily_reporter = models.BooleanField(
        '日報担当', default=False,
        help_text='ONの場合、この従業員がこの利用者の日報提出対象になる',
    )
    note = models.CharField('メモ', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('作成日時', auto_now_add=True)

    class Meta:
        verbose_name = '担当スケジュール'
        verbose_name_plural = '担当スケジュール'
        ordering = ['-date', 'employee_id']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'user', 'date'],
                name='unique_employee_user_date',
            ),
        ]

    def __str__(self):
        return f'{self.date} {self.employee} → {self.user}'

    @property
    def time_label(self):
        if self.start_time and self.end_time:
            return f'{self.start_time:%H:%M}〜{self.end_time:%H:%M}'
        return ''


class ShiftPattern(models.Model):
    '''いつも通りのシフトの型（曜日ベース）

    「山田さんは毎週月・水に田中さんを担当（10:00-16:00、日報担当）」のような
    繰り返しパターン。月単位で Assignment に一括展開する（既存の日はスキップ）。
    '''
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        verbose_name='従業員', related_name='shift_patterns',
    )
    user = models.ForeignKey(
        'dashboard.User', on_delete=models.CASCADE,
        verbose_name='利用者', related_name='shift_patterns',
    )
    weekday = models.IntegerField('曜日', choices=WEEKDAY_CHOICES)
    start_time = models.TimeField('開始時刻', null=True, blank=True)
    end_time = models.TimeField('終了時刻', null=True, blank=True)
    is_daily_reporter = models.BooleanField('日報担当', default=False)
    is_active = models.BooleanField('有効', default=True)

    class Meta:
        verbose_name = 'シフトパターン'
        verbose_name_plural = 'シフトパターン'
        ordering = ['weekday', 'employee_id']
        constraints = [
            models.UniqueConstraint(
                fields=['employee', 'user', 'weekday'],
                name='unique_pattern_employee_user_weekday',
            ),
        ]

    def __str__(self):
        return f'{self.get_weekday_display()} {self.employee} → {self.user}'

    @classmethod
    def generate_assignments(cls, year, month):
        '''有効なパターンを指定月の Assignment に展開する。

        既に同じ（従業員×利用者×日付）の割当てがある日はスキップするため、
        個別に編集・削除した例外は上書きされない。戻り値は新規作成件数。
        '''
        created = 0
        days_in_month = calendar_module.monthrange(year, month)[1]
        patterns = cls.objects.filter(is_active=True).select_related('employee', 'user')
        for pattern in patterns:
            for day in range(1, days_in_month + 1):
                target = date_cls(year, month, day)
                if target.weekday() != pattern.weekday:
                    continue
                _, was_created = Assignment.objects.get_or_create(
                    employee=pattern.employee, user=pattern.user, date=target,
                    defaults={
                        'start_time': pattern.start_time,
                        'end_time': pattern.end_time,
                        'is_daily_reporter': pattern.is_daily_reporter,
                        'note': 'シフトパターンから生成',
                    },
                )
                created += int(was_created)
        return created


class Attendance(models.Model):
    '''出退勤記録（Slackのボタン押下または画面から登録）'''
    class Kind(models.TextChoices):
        CLOCK_IN = 'in', '出勤'
        CLOCK_OUT = 'out', '退勤'

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        verbose_name='従業員', related_name='attendances',
    )
    date = models.DateField('日付')
    kind = models.CharField('種別', max_length=3, choices=Kind.choices)
    timestamp = models.DateTimeField('打刻時刻')

    class Meta:
        verbose_name = '出退勤記録'
        verbose_name_plural = '出退勤記録'
        ordering = ['-date', 'employee_id', 'kind']
        constraints = [
            # 同日同種の二重打刻を防ぐ（Slack側は既存があればスキップする想定）
            models.UniqueConstraint(
                fields=['employee', 'date', 'kind'],
                name='unique_employee_date_kind',
            ),
        ]

    def __str__(self):
        return f'{self.date} {self.employee} {self.get_kind_display()}'
