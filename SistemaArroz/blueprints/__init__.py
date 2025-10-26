from functools import wraps
from flask import g, redirect, url_for, request, jsonify

def login_required(f):
    """
    Decorador que redirige a la página de login si el usuario no ha iniciado sesión.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            # Redirige a la página de login, guardando la URL a la que se intentaba acceder.
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    """
    Decorador para endpoints de API. Si el usuario no ha iniciado sesión,
    devuelve un error 401 en formato JSON en lugar de redirigir.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return jsonify({'error': 'Autenticación requerida'}), 401
        return f(*args, **kwargs)
    return decorated_function
