from flask import Blueprint, render_template, request, flash, redirect, url_for, session, g
from . import login_required
from logic import (
    verificar_usuario,
    registrar_nuevo_ingenio_y_jefe_logic,
    cambiar_password_logic
)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('main.compras'))
        
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        error = None
        user = verificar_usuario(email, password)

        if user is None:
            error = 'Email o contraseña incorrectos.'
        
        if error is None:
            session.clear()
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['nivel_acceso'] = user['nivel_acceso']
            session['ingenio_id'] = user['ingenio_id']
            session['ingenio_nombre'] = user['ingenio_nombre']
            if 'remember' in request.form:
                session.permanent = True
            return redirect(url_for('main.compras'))
        
        flash(error, 'danger')

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        return redirect(url_for('main.compras'))
    if request.method == 'POST':
        nombre_ingenio = request.form['nombre_ingenio']
        direccion = request.form['direccion']
        nit = request.form.get('nit', '').strip() or None
        celular = request.form['celular']
        email = request.form['email']
        password = request.form['password']
        try:
            registrar_nuevo_ingenio_y_jefe_logic(nombre_ingenio, email, password, direccion, nit, celular)
            flash('¡Ingenio registrado exitosamente! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.login'))
        except ValueError as e:
            flash(str(e), 'danger')

    return render_template('register.html')

@auth_bp.route('/cambiar_password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    if request.method == 'POST':
        try:
            cambiar_password_logic(g.user['id'], request.form['old_password'], request.form['new_password'], request.form['confirm_password'])
            flash('Contraseña actualizada exitosamente. Por favor, inicia sesión de nuevo.', 'success')
            return redirect(url_for('auth.logout'))
        except ValueError as e:
            flash(str(e), 'danger')
    
    return render_template('cambiar_password.html')
