from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.views import View
from django.utils import timezone
from apps.elections.models import Election
from apps.voters.models import Voter


def election_management_landing(request):
    # RBAC: Restrict polling unit staff to the voting station only
    if hasattr(request.user, 'staff_profile') and request.user.staff_profile.polling_unit:
        if request.user.staff_profile.role != 'election_admin' and not request.user.is_superuser:
            return redirect('voting:auth')
    
    election = Election.objects.filter(
        is_active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now(),
    ).order_by('-created_at').first()
    return redirect('elections:detail', pk=election.pk) if election else redirect('dashboard:home')


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return election_management_landing(request)
        return render(request, 'auth/login.html')

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Check if account is active
            if not user.is_active:
                messages.error(request, 'Your account has been deactivated. Please contact an administrator.')
                return render(request, 'auth/login.html')
                
            login(request, user)
            messages.success(request, 'Login successful!')
            return election_management_landing(request)
        else:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'auth/login.html')


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.info(request, 'You have been logged out securely.')
        return redirect('authentication:login')
    
    def get(self, request):
        logout(request)
        messages.info(request, 'You have been logged out.')
        return redirect('authentication:login')


class RegisterView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard:home')
        return render(request, 'auth/register.html')

    def post(self, request):
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        full_name = request.POST.get('full_name', '')

        if not username or not password or not confirm_password:
            messages.error(request, 'Username and Password are required.')
            return render(request, 'auth/register.html')
            
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'auth/register.html')
            
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists. Please choose another.')
            return render(request, 'auth/register.html')

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=full_name
            )
            Voter.objects.create(user=user)
            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('authentication:login')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, 'auth/register.html')