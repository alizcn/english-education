import json
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.subscriptions.models import Plan, Subscription, Payment, TrialUsage
from apps.quizzes.models import QuizSession
from apps.interviews.models import InterviewSession
from apps.accounts.models import UserLevel

from .decorators import superuser_required
from .registry import REGISTRY, get_resource, grouped_resources


User = get_user_model()
PAGE_SIZE = 25


def _common_context(active_slug=None, active_kind='resource'):
    return {
        'sections': grouped_resources(),
        'active_slug': active_slug,
        'active_kind': active_kind,
    }


def _build_form_class(model, fields=None, exclude=()):
    meta_attrs = {'model': model}
    if fields is not None:
        meta_attrs['fields'] = fields
    else:
        meta_attrs['exclude'] = tuple(exclude) if exclude else ()
    Meta = type('Meta', (), meta_attrs)
    return type(f'{model.__name__}Form', (forms.ModelForm,), {'Meta': Meta})


def _apply_search(qs, resource, q):
    if not q or not resource.search_fields:
        return qs
    cond = Q()
    for f in resource.search_fields:
        cond |= Q(**{f'{f}__icontains': q})
    return qs.filter(cond)


def _apply_filters(qs, resource, request):
    for field, _label in resource.filters:
        val = request.GET.get(field)
        if val in (None, ''):
            continue
        if val == '__null__':
            qs = qs.filter(**{f'{field}__isnull': True})
        elif val == '__notnull__':
            qs = qs.filter(**{f'{field}__isnull': False})
        else:
            qs = qs.filter(**{field: val})
    return qs


def _filter_options(resource):
    """Return [(field, label, [(value, label, is_selected_initially=False), ...])]
    Caller layers in 'is_selected' from request.GET."""
    out = []
    for field, label in resource.filters:
        try:
            mfield = resource.model._meta.get_field(field)
        except Exception:
            out.append((field, label, []))
            continue
        choices = []
        if getattr(mfield, 'choices', None):
            choices = [(str(v), str(lbl)) for v, lbl in mfield.choices]
        elif mfield.get_internal_type() == 'BooleanField':
            choices = [('True', 'Evet'), ('False', 'Hayır')]
        elif mfield.is_relation and mfield.related_model is not None:
            rel = mfield.related_model
            qs = rel._default_manager.all()[:200]
            choices = [(str(o.pk), str(o)) for o in qs]
        out.append((field, label, choices))
    return out


@superuser_required
def dashboard(request):
    now = timezone.now()
    today = now.date()
    week_ago = today - timedelta(days=6)
    month_ago = today - timedelta(days=29)

    user_total = User.objects.count()
    user_today = User.objects.filter(date_joined__date=today).count()
    user_week = User.objects.filter(date_joined__date__gte=week_ago).count()

    sub_active = Subscription.objects.filter(status=Subscription.STATUS_ACTIVE).count()
    sub_total = Subscription.objects.count()

    pay_success = Payment.objects.filter(status=Payment.STATUS_SUCCESS)
    revenue_total = pay_success.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    revenue_month = pay_success.filter(created_at__date__gte=month_ago).aggregate(s=Sum('amount'))['s'] or Decimal('0')
    revenue_today = pay_success.filter(created_at__date=today).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    quiz_sessions = QuizSession.objects.count()
    quiz_today = QuizSession.objects.filter(started_at__date=today).count()
    interview_total = InterviewSession.objects.count()

    # Daily revenue for last 30 days
    daily = (
        pay_success.filter(created_at__date__gte=month_ago)
        .annotate(d=TruncDate('created_at'))
        .values('d')
        .annotate(total=Sum('amount'), c=Count('id'))
        .order_by('d')
    )
    by_day = {r['d']: r for r in daily}
    chart_labels, chart_revenue, chart_count = [], [], []
    for i in range(30):
        d = month_ago + timedelta(days=i)
        chart_labels.append(d.strftime('%d/%m'))
        row = by_day.get(d)
        chart_revenue.append(float(row['total']) if row else 0)
        chart_count.append(row['c'] if row else 0)

    recent_payments = (
        Payment.objects.select_related('user', 'plan')
        .order_by('-created_at')[:8]
    )
    recent_users = User.objects.order_by('-date_joined')[:8]
    recent_subs = (
        Subscription.objects.select_related('user', 'plan')
        .order_by('-created_at')[:8]
    )

    plan_breakdown = (
        Subscription.objects.filter(status=Subscription.STATUS_ACTIVE)
        .values('plan__name')
        .annotate(c=Count('id'))
        .order_by('-c')
    )

    ctx = _common_context(active_kind='dashboard')
    ctx.update({
        'user_total': user_total,
        'user_today': user_today,
        'user_week': user_week,
        'sub_active': sub_active,
        'sub_total': sub_total,
        'revenue_total': revenue_total,
        'revenue_month': revenue_month,
        'revenue_today': revenue_today,
        'quiz_sessions': quiz_sessions,
        'quiz_today': quiz_today,
        'interview_total': interview_total,
        'chart_labels': json.dumps(chart_labels),
        'chart_revenue': json.dumps(chart_revenue),
        'chart_count': json.dumps(chart_count),
        'recent_payments': recent_payments,
        'recent_users': recent_users,
        'recent_subs': recent_subs,
        'plan_breakdown': plan_breakdown,
    })
    return render(request, 'superadmin/dashboard.html', ctx)


@superuser_required
def list_view(request, slug):
    resource = get_resource(slug)
    if not resource:
        raise Http404
    qs = resource.get_queryset()
    q = request.GET.get('q', '').strip()
    qs = _apply_search(qs, resource, q)
    qs = _apply_filters(qs, resource, request)

    total = qs.count()
    try:
        page = max(1, int(request.GET.get('page', '1')))
    except ValueError:
        page = 1
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    offset = (page - 1) * PAGE_SIZE
    rows = list(qs[offset:offset + PAGE_SIZE])

    cells = []
    for obj in rows:
        cells.append({
            'obj': obj,
            'pk': obj.pk,
            'values': [resource.cell(obj, c) for c in resource.list_columns],
        })

    # Build filter UI with selected values
    filter_ui = []
    for field, label, choices in _filter_options(resource):
        current = request.GET.get(field, '')
        filter_ui.append({
            'field': field,
            'label': label,
            'choices': choices,
            'current': current,
        })

    ctx = _common_context(active_slug=slug)
    ctx.update({
        'resource': resource,
        'rows': cells,
        'q': q,
        'page': page,
        'pages': pages,
        'total': total,
        'page_size': PAGE_SIZE,
        'filter_ui': filter_ui,
        'has_prev': page > 1,
        'has_next': page < pages,
    })
    return render(request, 'superadmin/list.html', ctx)


@superuser_required
def detail_view(request, slug, pk):
    resource = get_resource(slug)
    if not resource:
        raise Http404
    obj = get_object_or_404(resource.get_queryset(), pk=pk)

    field_rows = []
    for f in resource.model._meta.get_fields():
        if f.is_relation and f.one_to_many:
            continue
        if f.is_relation and f.many_to_many:
            try:
                value = ', '.join(str(o) for o in getattr(obj, f.name).all()[:20])
            except Exception:
                value = ''
        else:
            value = getattr(obj, f.name, '')
            if callable(value):
                try:
                    value = value()
                except Exception:
                    value = ''
        field_rows.append((f.verbose_name if hasattr(f, 'verbose_name') else f.name, value))

    extra_rows = []
    for attr, label in resource.detail_extra:
        if callable(attr):
            extra_rows.append((label, attr(obj)))
        elif hasattr(resource, attr) and callable(getattr(resource, attr)):
            extra_rows.append((label, getattr(resource, attr)(obj)))
        else:
            extra_rows.append((label, getattr(obj, attr, '')))

    ctx = _common_context(active_slug=slug)
    ctx.update({
        'resource': resource,
        'obj': obj,
        'field_rows': field_rows,
        'extra_rows': extra_rows,
    })
    return render(request, 'superadmin/detail.html', ctx)


@superuser_required
def create_view(request, slug):
    resource = get_resource(slug)
    if not resource or not resource.can_create:
        raise Http404
    FormCls = _build_form_class(resource.model, resource.form_fields, resource.form_exclude)
    if request.method == 'POST':
        form = FormCls(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f'{resource.label_singular} oluşturuldu.')
            return redirect('superadmin:detail', slug=slug, pk=obj.pk)
    else:
        form = FormCls()
    ctx = _common_context(active_slug=slug)
    ctx.update({'resource': resource, 'form': form, 'mode': 'create'})
    return render(request, 'superadmin/form.html', ctx)


@superuser_required
def update_view(request, slug, pk):
    resource = get_resource(slug)
    if not resource or not resource.can_edit:
        raise Http404
    obj = get_object_or_404(resource.get_queryset(), pk=pk)
    FormCls = _build_form_class(resource.model, resource.form_fields, resource.form_exclude)
    if request.method == 'POST':
        form = FormCls(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'{resource.label_singular} güncellendi.')
            return redirect('superadmin:detail', slug=slug, pk=obj.pk)
    else:
        form = FormCls(instance=obj)
    ctx = _common_context(active_slug=slug)
    ctx.update({'resource': resource, 'form': form, 'obj': obj, 'mode': 'edit'})
    return render(request, 'superadmin/form.html', ctx)


@superuser_required
def delete_view(request, slug, pk):
    resource = get_resource(slug)
    if not resource or not resource.can_delete:
        raise Http404
    obj = get_object_or_404(resource.get_queryset(), pk=pk)
    if request.method == 'POST':
        label = str(obj)
        obj.delete()
        messages.success(request, f'{resource.label_singular} silindi: {label}')
        return redirect('superadmin:list', slug=slug)
    ctx = _common_context(active_slug=slug)
    ctx.update({'resource': resource, 'obj': obj})
    return render(request, 'superadmin/delete.html', ctx)


# ---------- Special actions ----------

class AssignPlanForm(forms.Form):
    plan = forms.ModelChoiceField(queryset=Plan.objects.filter(is_active=True), label='Plan')
    activate_now = forms.BooleanField(required=False, initial=True, label='Hemen aktive et')


@superuser_required
def assign_plan(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = AssignPlanForm(request.POST)
        if form.is_valid():
            plan = form.cleaned_data['plan']
            sub = Subscription.objects.create(
                user=user, plan=plan,
                status=Subscription.STATUS_PENDING,
            )
            if form.cleaned_data['activate_now']:
                sub.activate()
            messages.success(request, f"{user} kullanıcısına {plan.name} planı atandı.")
            return redirect('superadmin:detail', slug='users', pk=user.pk)
    else:
        form = AssignPlanForm()
    ctx = _common_context(active_slug='users')
    ctx.update({'target_user': user, 'form': form})
    return render(request, 'superadmin/assign_plan.html', ctx)
