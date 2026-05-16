from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from .forms import RegisterForm, LoginForm
from django.contrib import messages
from django.contrib.auth import get_user_model

User = get_user_model()


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, "Registration successful.")
            return redirect("/")
    else:
        form = RegisterForm()
    return render(request, "users/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            identifier = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            # Allow login via email or username
            user = None
            try:
                if "@" in identifier:
                    user_obj = User.objects.get(email__iexact=identifier)
                    username = user_obj.get_username()
                    user = authenticate(request, username=username, password=password)
                else:
                    user = authenticate(request, username=identifier, password=password)
            except User.DoesNotExist:
                user = None

            if user is not None:
                auth_login(request, user)
                return redirect(request.GET.get("next") or "/")
            else:
                messages.error(request, "Invalid credentials")
    else:
        form = LoginForm()
    return render(request, "users/login.html", {"form": form})


def logout_view(request):
    auth_logout(request)
    return redirect(reverse("users:login"))


@login_required
def profile_view(request):
    return render(request, "users/profile.html", {"user": request.user})


def staff_required(view_func):
    return user_passes_test(lambda u: u.is_staff)(view_func)


@staff_required
def admin_users_view(request):
    users = User.objects.all().order_by("-date_joined")
    return render(request, "users/admin_users.html", {"users": users})
from django.shortcuts import render

# Create your views here.
