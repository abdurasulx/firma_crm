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
    return render(request, 'analytics_dashboard.html')
