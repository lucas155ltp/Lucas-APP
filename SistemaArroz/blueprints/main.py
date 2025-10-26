from flask import Blueprint, render_template, request, g, session, send_file, jsonify
from datetime import datetime, timedelta
import calendar
import pandas as pd
from io import BytesIO
from . import login_required
from logic import (
    obtener_productos,
    obtener_almacenes_por_ingenio_logic,
    obtener_variedades_por_ingenio_logic,
    obtener_estadisticas_dashboard_logic,
    obtener_inventario_logic,
    obtener_historial_transacciones_logic
)
from logger import setup_logger

main_bp = Blueprint('main', __name__)
logger = setup_logger()

def procesar_filtros_de_fecha(args):
    """
    Centraliza la lógica para procesar los filtros de fecha desde los argumentos de la request.
    Devuelve (fecha_inicio, fecha_fin, titulo_periodo).
    """
    hoy = datetime.now()
    periodo_tipo = args.get('periodo_tipo', 'ultimos_30_dias')
    
    meses_disponibles = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'), (5, 'Mayo'), (6, 'Junio'),
        (7, 'Julio'), (8, 'Agosto'), (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]

    if periodo_tipo == 'mensual':
        mes = int(args.get('mes', hoy.month))
        año = int(args.get('año', hoy.year))
        _, ultimo_dia = calendar.monthrange(año, mes)
        fecha_inicio = f"{año}-{mes:02d}-01"
        fecha_fin = f"{año}-{mes:02d}-{ultimo_dia}"
        titulo_periodo = f"{dict(meses_disponibles)[mes]} {año}"
    elif periodo_tipo == 'temporada':
        temporada = args.get('temporada', 'zafra')
        año = int(args.get('año', hoy.year))
        if temporada == 'zafra':
            fecha_inicio, fecha_fin = f"{año}-02-01", f"{año}-05-31"
            titulo_periodo = f"Zafra {año}"
        else: # Descanso
            fecha_inicio, fecha_fin = f"{año}-06-01", f"{año + 1}-01-31"
            titulo_periodo = f"Descanso {año}-{año+1}"
    else: # Default: ultimos_30_dias o 'todos'
        fecha_fin_dt = hoy
        fecha_inicio_dt = fecha_fin_dt - timedelta(days=29)
        fecha_inicio, fecha_fin = fecha_inicio_dt.strftime('%Y-%m-%d'), fecha_fin_dt.strftime('%Y-%m-%d')
        titulo_periodo = "Últimos 30 días"
        
    return fecha_inicio, fecha_fin, titulo_periodo

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Muestra el panel de estadísticas y finanzas."""
    hoy = datetime.now()
    periodo_tipo = request.args.get('periodo_tipo', 'ultimos_30_dias')
    
    # Determinar el rango de fechas basado en los filtros
    fecha_inicio, fecha_fin, titulo_periodo = procesar_filtros_de_fecha(request.args)

    stats = obtener_estadisticas_dashboard_logic(g.user['ingenio_id'], fecha_inicio, fecha_fin)
    
    # Valores para los selectores del formulario
    años_disponibles = list(range(hoy.year, hoy.year - 5, -1))
    meses_disponibles = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'), (5, 'Mayo'), (6, 'Junio'),
        (7, 'Julio'), (8, 'Agosto'), (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    
    return render_template('dashboard.html', stats=stats, 
                           titulo_periodo=titulo_periodo,
                           años=años_disponibles,
                           meses=meses_disponibles,
                           filtros_activos=request.args)

@main_bp.route('/compras')
@login_required
def compras():
    productos = obtener_productos()
    almacenes = obtener_almacenes_por_ingenio_logic(g.user['ingenio_id'])
    variedades = obtener_variedades_por_ingenio_logic(g.user['ingenio_id'])
    return render_template('index.html', productos=productos, almacenes=almacenes, variedades=variedades)

@main_bp.route('/carrito')
@login_required
def carrito():
    """Muestra el carrito de venta actual desde la sesión."""
    carrito = session.get('carrito', {})
    total = sum(item.get('cantidad', 0) * item.get('precio', 0) for item in carrito.values()) if isinstance(carrito, dict) else 0
    return render_template('carrito.html', carrito=carrito, total=total)

@main_bp.route('/inventario')
@login_required
def inventario():
    filtro_producto_id_str = request.args.get('producto_id', '').strip()
    filtro_lote = request.args.get('lote', '').strip()
    filtro_variedad = request.args.get('variedad', '').strip()
    filtro_fecha_inicio = request.args.get('fecha_inicio', '').strip()
    filtro_fecha_fin = request.args.get('fecha_fin', '').strip()
    filtro_almacen_id_str = request.args.get('almacen_id', '').strip()

    filtro_producto_id = int(filtro_producto_id_str) if filtro_producto_id_str else None
    filtro_almacen_id = int(filtro_almacen_id_str) if filtro_almacen_id_str else None

    inventario_data = obtener_inventario_logic(
        ingenio_id=g.user['ingenio_id'],
        producto_id=filtro_producto_id,
        lote=filtro_lote,
        variedad=filtro_variedad,
         fecha_inicio=filtro_fecha_inicio,
        fecha_fin=filtro_fecha_fin,
        almacen_id=filtro_almacen_id
    )
    
    productos_para_filtro = obtener_productos()
    almacenes_para_filtro = obtener_almacenes_por_ingenio_logic(g.user['ingenio_id'])

    return render_template(
        'inventario.html', 
        inventario=inventario_data,
        productos=productos_para_filtro,
        almacenes=almacenes_para_filtro,
        filtros_activos=request.args
    )

@main_bp.route('/historial')
@login_required
def historial():
    hoy = datetime.now()
    periodo_tipo = request.args.get('periodo_tipo')
    fecha_inicio, fecha_fin = None, None

    if periodo_tipo in ['mensual', 'temporada']:
        fecha_inicio, fecha_fin, _ = procesar_filtros_de_fecha(request.args)
    elif periodo_tipo == 'rango':
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
    # Si es 'todos' o no está definido, fecha_inicio y fecha_fin permanecen como None,
    # lo que significa que se buscará en todo el historial.

    historial_data = obtener_historial_transacciones_logic(
        ingenio_id=g.user['ingenio_id'],
        tipo=request.args.get('tipo', '').strip() or None,
        producto_id=request.args.get('producto_id', type=int) or None,
        nombre=request.args.get('nombre', '').strip() or None,
        lote=request.args.get('lote', '').strip() or None,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )
    
    productos_para_filtro = obtener_productos()
    años_disponibles = list(range(hoy.year, hoy.year - 5, -1))
    meses_disponibles = [(m, calendar.month_name[m]) for m in range(1, 13)]

    return render_template('historial.html', 
                           historial=historial_data, 
                           productos=productos_para_filtro,
                           filtros_activos=request.args,
                           años=años_disponibles,
                           meses=meses_disponibles)

@main_bp.route('/welcome')
def welcome():
    """
    Returns a welcome message
    """
    logger.info(f"Request received: {request.method} {request.path}")
    return jsonify({'message': 'Welcome to the SistemaArroz API!'})

@main_bp.route('/dashboard/export_excel')
@login_required
def dashboard_export_excel():
    """Exporta los datos del dashboard a un archivo Excel."""
    # Determinar el rango de fechas basado en los filtros
    fecha_inicio, fecha_fin, titulo_periodo = procesar_filtros_de_fecha(request.args)

    stats = obtener_estadisticas_dashboard_logic(g.user['ingenio_id'], fecha_inicio, fecha_fin)

    # Crear un buffer en memoria para el archivo Excel
    output = BytesIO()

    # Crear el archivo Excel con múltiples hojas
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja 1: Resumen de Estadísticas
        resumen_data = {
            'Métrica': [
                'Ingresos por Ventas',
                'Costos de Compras',
                'Ingresos por Servicios',
                'Balance General',
                'Valor de Inventario',
                'Lotes Activos'
            ],
            'Valor': [
                stats.get('total_ventas', 0),
                stats.get('total_compras', 0),
                stats.get('total_servicios', 0),
                stats.get('balance', 0),
                stats.get('valor_inventario', 0),
                stats.get('lotes_activos', 0)
            ],
            'Período': [titulo_periodo] * 6
        }
        df_resumen = pd.DataFrame(resumen_data)
        df_resumen.to_excel(writer, sheet_name='Resumen', index=False)

        # Hoja 2: Ventas Agrupadas
        ventas_data = [{'Fecha': item['fecha'], 'Total Ventas': item['total']} for item in stats.get('ventas_agrupadas', [])]
        df_ventas = pd.DataFrame(ventas_data)
        df_ventas.to_excel(writer, sheet_name='Ventas', index=False)

        # Hoja 3: Inventario por Producto
        inventario_data = [{'Producto': label, 'Valor': value} for label, value in zip(
            stats.get('inventario_chart_data', {}).get('labels', []),
            stats.get('inventario_chart_data', {}).get('data', [])
        )]
        df_inventario = pd.DataFrame(inventario_data)
        df_inventario.to_excel(writer, sheet_name='Inventario', index=False)

    output.seek(0)

    # Nombre del archivo con timestamp
    filename = f"dashboard_{titulo_periodo.replace(' ', '_').replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
