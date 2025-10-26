from flask import Flask, render_template, request, flash, redirect, url_for, session, g, make_response, jsonify
from functools import wraps
import os
import logging
from jinja2 import pass_context


def create_app():
    app = Flask(__name__)

    # Configuración segura: SECRET_KEY desde variable de entorno o archivo .env cargado por el entorno
    secret = os.getenv('SECRET_KEY')
    if not secret:
        # Fallback para desarrollo: generar una clave temporal en tiempo de ejecución
        # Recomendado: definir SECRET_KEY en variables de entorno en producción
        secret = os.urandom(24).hex()
    app.secret_key = secret

    # Set up logger
    logger = logging.getLogger('flask-api-service')
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # --- Filtro Jinja2 personalizado para mostrar unidades ---
    @pass_context
    def mostrar_unidades_filter(context, cantidad_kg, unidad_original, cantidad_original):
        if not isinstance(cantidad_kg, (int, float)) or cantidad_kg < 0:
            return f"{cantidad_original:.2f} {unidad_original}"

        KG_POR_QUINTAL = 46
        KG_POR_FANEGA = 200

        if unidad_original == 'quintal':
            cantidad_fanegas = cantidad_kg / KG_POR_FANEGA
            return f"{cantidad_original:.2f} quintales ({cantidad_fanegas:.2f} fanegas)"
        elif unidad_original == 'fanega':
            cantidad_quintales = cantidad_kg / KG_POR_QUINTAL
            return f"{cantidad_original:.2f} fanegas ({cantidad_quintales:.2f} quintales)"
        return f"{cantidad_original:.2f} {unidad_original}"

    app.jinja_env.filters['mostrar_unidades'] = mostrar_unidades_filter
    # Importar Blueprints aquí para evitar importaciones circulares
    from blueprints.main import main_bp
    from blueprints.auth import auth_bp
    from blueprints.transactions import transactions_bp
    from blueprints.reports import reports_bp
    from blueprints.management import management_bp

    @app.after_request
    def add_no_cache_headers(response):
        """Añade cabeceras para evitar que el navegador guarde la página en caché."""
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    @app.before_request
    def load_logged_in_user():
        user_id = session.get('user_id')
        if user_id:
            # Fetch additional ingenio details
            from db import obtener_ingenio_por_id_db
            ingenio_id = session.get('ingenio_id')
            ingenio_details = obtener_ingenio_por_id_db(ingenio_id) if ingenio_id else None
            g.user = {
                'id': user_id,
                'email': session.get('email'),
                'nivel_acceso': session.get('nivel_acceso'),
                'ingenio_id': ingenio_id,
                'ingenio_nombre': session.get('ingenio_nombre'),
                'ingenio_direccion': ingenio_details[2] if ingenio_details else None,
                'ingenio_nit': ingenio_details[3] if ingenio_details else None,
                'ingenio_celular': ingenio_details[4] if ingenio_details else None
            }
        else:
            g.user = None

    @app.route('/')
    def root():
        if g.user:
            return redirect(url_for('main.compras'))
        return redirect(url_for('auth.login'))

    # Registrar Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(management_bp)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
