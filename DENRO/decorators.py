# decorators.py
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def login_required(view_func):
    """Decorator to ensure user is logged in"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.session.get("user_id"):
            messages.error(request, "Please log in to access this page.")
            return redirect("login")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def role_required(allowed_roles):
    """Decorator to ensure user has one of the specified roles"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.session.get("user_id"):
                messages.error(request, "Please log in to access this page.")
                return redirect("login")
            
            user_role = request.session.get("role", "").lower()
            if user_role not in [role.lower() for role in allowed_roles]:
                messages.error(request, "You don't have permission to access this page.")
                # Redirect to appropriate dashboard based on user's role
                role_redirects = {
                    "super admin": "SA-dashboard",
                    "admin": "Admin-dashboard", 
                    "penro": "PENRO-dashboard",
                    "cenro": "CENRO-dashboard"
                }
                return redirect(role_redirects.get(user_role, "login"))
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def can_create_users(view_func):
    """Decorator to ensure user can create other users"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.session.get("user_id"):
            messages.error(request, "Please log in to access this page.")
            return redirect("login")
        
        user_role = request.session.get("role", "").lower()
        # Only these roles can create users
        can_create_roles = ["super admin", "admin", "penro", "cenro"]
        
        if user_role not in can_create_roles:
            messages.error(request, "You don't have permission to create user accounts.")
            # Redirect to appropriate dashboard
            role_redirects = {
                "super admin": "SA-dashboard",
                "admin": "Admin-dashboard", 
                "penro": "PENRO-dashboard",
                "cenro": "CENRO-dashboard",
                "evaluator": "login"  # Evaluators don't have a specific dashboard mentioned
            }
            return redirect(role_redirects.get(user_role, "login"))
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view