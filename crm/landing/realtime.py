import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Count
from django.utils import timezone

from main.models import Company, PlanRequest, User


def get_superadmin_payload():
    now = timezone.now()
    yesterday = now - timezone.timedelta(days=1)

    labels = []
    chart_data = []
    for i in range(6, -1, -1):
        day = now.date() - timezone.timedelta(days=i)
        labels.append(day.strftime('%d-%b'))
        chart_data.append(Company.objects.filter(created_at__date=day).count())

    recent_companies = []
    for company in Company.objects.order_by('-created_at')[:5]:
        if company.setup_mode:
            status = 'Sozlanyapti'
            status_class = 'warning'
        elif company.is_on_trial:
            status = 'Sinovda'
            status_class = 'primary'
        elif company.is_active:
            status = 'Faol'
            status_class = 'success'
        else:
            status = "To'xtatilgan"
            status_class = 'danger'

        recent_companies.append({
            'name': company.name,
            'subdomain': company.subdomain,
            'created_at': timezone.localtime(company.created_at).strftime('%d.%m.%Y'),
            'status': status,
            'status_class': status_class,
        })

    return {
        'type': 'superadmin_update',
        'stats': {
            'total_companies': Company.objects.count(),
            'active_companies': Company.objects.filter(is_active=True).count(),
            'trial_companies': Company.objects.filter(is_on_trial=True).count(),
            'setup_companies': Company.objects.filter(setup_mode=True).count(),
            'total_users': User.objects.count(),
            'today_registrations': Company.objects.filter(created_at__gte=yesterday).count(),
            'pending_plan_requests': PlanRequest.objects.filter(status='pending').count(),
        },
        'chart': {
            'labels': labels,
            'data': chart_data,
        },
        'recent_companies': recent_companies,
    }


def get_superadmin_context():
    payload = get_superadmin_payload()
    stats = payload['stats']
    context = {
        **stats,
        'recent_companies': Company.objects.all().order_by('-created_at')[:5],
        'chart_labels': json.dumps(payload['chart']['labels']),
        'chart_data': json.dumps(payload['chart']['data']),
    }
    return context


def broadcast_superadmin_update():
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        'superadmin',
        {
            'type': 'send_superadmin_update',
            'payload': get_superadmin_payload(),
        },
    )
