"""
Analytics Dashboard View
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .plan_utils import company_has_access


@login_required
def analytics_dashboard(request):
    """
    Display analytics dashboard with AI-powered demand forecasting.
    """
    # Check if plan has analytics feature
    if not getattr(request, 'has_analytics', False):
        messages.warning(request, "Sizning tarifingizda AI Analytics mavjud emas. Davom etish uchun tarifni yangilang.")
        return redirect('main')
    
    # Check if company has paid (or is on trial)
    if not company_has_access(request.company):
        messages.warning(request, "AI Analytics dan foydalanish uchun to'lov amalga oshirilgan bo'lishi kerak.")
        return redirect('main')
        
    return render(request, 'analytics_dashboard.html')
