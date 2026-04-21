from django.contrib.auth.backends import ModelBackend

from .models import User


class CompanyAwareModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        username = username or kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None

        queryset = User.objects.all()

        if request is not None and getattr(request, "company", None):
            queryset = queryset.filter(company=request.company)
        elif request is not None and getattr(request, "is_admin_panel", False):
            queryset = queryset.filter(is_superuser=True)

        for user in queryset.filter(username=username):
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None
