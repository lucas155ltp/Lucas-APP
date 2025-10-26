from flask import Blueprint, render_template, request, flash, redirect, url_for, g
from . import login_required
from logic import (
    crear_usuario_logic,
    crear_ingenio_logic,
    obtener_ingenios_logic,
    actualizar_ingenio_logic,
    crear_almacen_logic,
    obtener_almacenes_por_ingenio_logic,
    crear_variedad_logic,
    obtener_variedades_por_ingenio_logic,
    obtener_usuarios_por_ingenio_logic,
    toggle_acceso_usuario_logic
)

management_bp = Blueprint('management', __name__)

def jefe_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if g.user['nivel_acceso'] != 'jefe':
            flash('No tienes permiso para acceder a esta página.', 'danger')
            return redirect(url_for('main.compras'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@management_bp.route('/crear_usuario', methods=['GET', 'POST'])
@jefe_required
def crear_usuario():
    if request.method == 'POST':
        try:
            crear_usuario_logic(request.form['email'], request.form['password'], request.form['nivel_acceso'], g.user['ingenio_id'])
            flash(f"Usuario '{request.form['email']}' creado exitosamente.", 'success')
            return redirect(url_for('management.gestionar_usuarios'))
        except ValueError as e:
            flash(str(e), 'danger')
    return render_template('crear_usuario.html')

@management_bp.route('/ingenios', methods=['GET', 'POST'])
@jefe_required
def ingenios():
    if request.method == 'POST':
        try:
            crear_ingenio_logic(
                request.form.get('nombre', '').strip(),
                request.form.get('direccion', '').strip(),
                request.form.get('nit', '').strip() or None,
                request.form.get('celular', '').strip()
            )
            flash(f"Ingenio '{request.form.get('nombre')}' creado exitosamente.", 'success')
        except ValueError as e:
            flash(str(e), 'danger')
        return redirect(url_for('management.ingenios'))
    lista_ingenios = obtener_ingenios_logic()
    return render_template('ingenios.html', ingenios=lista_ingenios)

@management_bp.route('/gestionar_almacenes', methods=['GET', 'POST'])
@jefe_required
def gestionar_almacenes():
    if request.method == 'POST':
        try:
            crear_almacen_logic(request.form.get('nombre', '').strip(), g.user['ingenio_id'])
            flash(f"Almacén '{request.form.get('nombre')}' creado exitosamente.", 'success')
        except ValueError as e:
            flash(str(e), 'danger')
        return redirect(url_for('management.gestionar_almacenes'))
    lista_almacenes = obtener_almacenes_por_ingenio_logic(g.user['ingenio_id'])
    return render_template('gestionar_almacenes.html', almacenes=lista_almacenes)

@management_bp.route('/gestionar_variedades', methods=['GET', 'POST'])
@jefe_required
def gestionar_variedades():
    if request.method == 'POST':
        try:
            crear_variedad_logic(request.form.get('nombre', '').strip(), g.user['ingenio_id'])
            flash(f"Variedad '{request.form.get('nombre')}' creada exitosamente.", 'success')
        except ValueError as e:
            flash(str(e), 'danger')
        return redirect(url_for('management.gestionar_variedades'))
    lista_variedades = obtener_variedades_por_ingenio_logic(g.user['ingenio_id'])
    return render_template('gestionar_variedades.html', variedades=lista_variedades)

@management_bp.route('/gestionar_usuarios')
@jefe_required
def gestionar_usuarios():
    usuarios_list = obtener_usuarios_por_ingenio_logic(g.user['ingenio_id'])
    return render_template('gestionar_usuarios.html', usuarios=usuarios_list)

@management_bp.route('/toggle_acceso/<int:user_id>', methods=['POST'])
@jefe_required
def toggle_acceso(user_id):
    try:
        toggle_acceso_usuario_logic(user_id, g.user['id'])
        flash('Estado del usuario actualizado correctamente.', 'success')
    except (ValueError, PermissionError) as e:
        flash(str(e), 'danger')
    return redirect(url_for('management.gestionar_usuarios'))

@management_bp.route('/editar_ingenio', methods=['GET', 'POST'])
@jefe_required
def editar_ingenio():
    if request.method == 'POST':
        try:
            actualizar_ingenio_logic(
                g.user['ingenio_id'],
                request.form.get('nombre', '').strip(),
                request.form.get('direccion', '').strip(),
                request.form.get('nit', '').strip() or None,
                request.form.get('celular', '').strip()
            )
            flash("Perfil del ingenio actualizado exitosamente.", 'success')
            return redirect(url_for('main.dashboard'))
        except ValueError as e:
            flash(str(e), 'danger')
    # Pre-fill the form with current ingenio data
    ingenio_data = {
        'nombre': g.user['ingenio_nombre'],
        'direccion': g.user['ingenio_direccion'],
        'nit': g.user['ingenio_nit'],
        'celular': g.user['ingenio_celular']
    }
    return render_template('editar_ingenio.html', ingenio=ingenio_data)
