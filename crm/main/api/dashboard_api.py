from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..analytics.services import get_dashboard_stats

@login_required
def dashboard_stats_api(request):
    """API endpoint for dashboard statistics."""
    if request.user.type != 'ega':
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    stats = get_dashboard_stats()
    return JsonResponse(stats)
