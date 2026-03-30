"""
Analytics Dashboard View
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def analytics_dashboard(request):
    """
    Display analytics dashboard with AI-powered demand forecasting.
    """
    # Check if plan has analytics
    if not getattr(request, 'has_analytics', False):
        from django.contrib import messages
        from django.shortcuts import redirect
        messages.warning(request, "Sizning tarifingizda AI Analytics mavjud emas. Davom etish uchun tarifni yangilang.")
        return redirect('main')
        
    return render(request, 'analytics_dashboard.html')
