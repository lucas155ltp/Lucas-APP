from flask import Blueprint, render_template, request, flash, redirect, url_for, session, g
from . import login_required
from logic import (
    obtener_productos,
    obtener_almacenes_por_ingenio_logic,
    obtener_variedades_por_ingenio_logic,
    lote_existe_logic,
    registrar_compra_completa_logic,
    obtener_item_inventario_por_id,
    registrar_venta_multiproducto_logic,
    actualizar_precio_venta_logic,
    obtener_transaccion_completa_por_id_logic,
    registrar_devolucion_logic,
    obtener_lotes_transformables_logic,
    registrar_transformacion_logic,
    obtener_lotes_secables_logic,
    secar_lote_logic,
    registrar_servicio_secado_cliente_logic,
    registrar_servicio_pelado_cliente_logic
)

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route('/compras', methods=['POST'])
@login_required
def registrar_compra():
    try:
        productos = obtener_productos()
        producto_id = int(request.form.get('producto_id', 0))
        variedad = request.form.get('variedad', '').strip()
        lote = request.form.get('lote', '').strip()

        if lote_existe_logic(lote, g.user['ingenio_id']):
            raise ValueError(f"El número de lote '{lote}' ya existe. Por favor, ingrese uno diferente.")

        req_variedad = {p[0]: p[2] for p in productos}.get(producto_id, 0)
        if req_variedad and not variedad:
            raise ValueError('Este producto requiere que ingrese una variedad.')

        registrar_compra_completa_logic(
            ingenio_id=g.user['ingenio_id'],
            proveedor=request.form.get('proveedor', '').strip(),
            producto_id=producto_id,
            variedad=variedad,
            cantidad=float(request.form.get('unidades', '0') or 0),
            unidad=request.form.get('tipo_unidad', 'quintal'),
            precio=float(request.form.get('precio', '0') or 0),
            estado=request.form.get('estado', 'mojado'),
            almacen_id=int(request.form.get('almacen_id', 0)),
            lote=lote
        )
        flash(f"Compra del lote '{lote}' registrada exitosamente.", 'success')
    except Exception as e:
        flash(f'Error al registrar la compra: {e}', 'danger')
    return redirect(url_for('main.compras'))

@transactions_bp.route('/agregar_al_carrito/<int:item_id>', methods=['GET', 'POST'])
@login_required
def agregar_al_carrito(item_id):
    item = obtener_item_inventario_por_id(g.user['ingenio_id'], item_id)
    if not item:
        flash('El item de inventario no existe.', 'danger')
        return redirect(url_for('main.inventario'))

    if item[4] <= 0: # item[4] es la cantidad
        flash('Este item no tiene stock disponible.', 'warning')
        return redirect(url_for('main.inventario'))

    if request.method == 'POST':
        try:
            cantidad = float(request.form.get('cantidad', '0') or 0)
            precio = float(request.form.get('precio', '0') or 0)

            if cantidad <= 0 or precio <= 0:
                raise ValueError("Cantidad y precio deben ser mayores a cero.")
            if cantidad > item[4]:
                raise ValueError("No puedes añadir más de la cantidad disponible en stock.")

            if 'carrito' not in session:
                session['carrito'] = {}

            session['carrito'][str(item_id)] = {
                'producto_id': item[6], 'nombre_producto': item[1], 'variedad': item[2],
                'lote': item[3], 'cantidad': cantidad, 'unidad': item[6], 'precio': precio,
                'stock_disponible': item[4],
                'cantidad_kg_disponible': item[5]
            }
            session.modified = True
            flash(f"'{item[1]} - Lote {item[3]}' añadido al carrito.", 'success')
            return redirect(url_for('main.inventario'))
        except Exception as e:
            flash(f'Error al añadir al carrito: {e}', 'danger')
            return redirect(url_for('transactions.agregar_al_carrito', item_id=item_id))

    return render_template('agregar_al_carrito.html', item=item)

@transactions_bp.route('/carrito')
@login_required
def carrito():
    carrito_items = session.get('carrito', {})
    total = sum(item['cantidad'] * item['precio'] for item in carrito_items.values())
    return render_template('carrito.html', carrito=carrito_items, total_carrito=total)

@transactions_bp.route('/eliminar_del_carrito/<string:item_id>')
@login_required
def eliminar_del_carrito(item_id):
    if 'carrito' in session and item_id in session['carrito']:
        session['carrito'].pop(item_id)
        session.modified = True
        flash('Item eliminado del carrito.', 'success')
    return redirect(url_for('transactions.carrito'))

@transactions_bp.route('/finalizar_venta', methods=['POST'])
@login_required
def finalizar_venta():
    action = request.form.get('action')
    carrito_actual = session.get('carrito', {})

    if action == 'update':
        for item_id, item in carrito_actual.items():
            nueva_cantidad = float(request.form.get(f'cantidad_{item_id}', item['cantidad']))
            if 0 < nueva_cantidad <= item['stock_disponible']:
                session['carrito'][item_id]['cantidad'] = nueva_cantidad
        session.modified = True
        flash('Cantidades actualizadas.', 'info')
        return redirect(url_for('transactions.carrito'))

    elif action == 'finalize':
        try:
            registrar_venta_multiproducto_logic(g.user['ingenio_id'], request.form.get('comprador', '').strip(), request.form.get('observaciones', '').strip(), carrito_actual)
            session.pop('carrito', None)
            flash('Venta finalizada y registrada exitosamente.', 'success')
            return redirect(url_for('main.historial'))
        except ValueError as e:
            flash(f'Error al finalizar la venta: {e}', 'danger')
            return redirect(url_for('transactions.carrito'))
    
    return redirect(url_for('transactions.carrito'))

@transactions_bp.route('/fijar_precio/<int:item_id>', methods=['GET', 'POST'])
@login_required
def fijar_precio(item_id):
    if g.user['nivel_acceso'] == 'empleado':
        flash('No tienes permiso para acceder a esta página.', 'danger')
        return redirect(url_for('main.inventario'))

    item = obtener_item_inventario_por_id(g.user['ingenio_id'], item_id)
    if not item:
        flash('El item de inventario no existe.', 'danger')
        return redirect(url_for('main.inventario'))

    if request.method == 'POST':
        try:
            nuevo_precio = float(request.form.get('nuevo_precio', '0') or 0)
            actualizar_precio_venta_logic(g.user['ingenio_id'], item_id, nuevo_precio)
            flash('Precio de venta actualizado correctamente.', 'success')
            return redirect(url_for('main.inventario'))
        except Exception as e:
            flash(f'Error al actualizar el precio: {e}', 'danger')
    return render_template('fijar_precio.html', item=item)

@transactions_bp.route('/devolucion/<int:transaccion_id>', methods=['GET', 'POST'])
@login_required
def registrar_devolucion(transaccion_id):
    transaccion_original = obtener_transaccion_completa_por_id_logic(transaccion_id, g.user['ingenio_id'])
    if not transaccion_original or transaccion_original['tipo'] != 'venta':
        flash('La transacción no es una venta válida o no existe.', 'danger')
        return redirect(url_for('main.historial'))

    if request.method == 'POST':
        try:
            cantidad_devuelta = float(request.form.get('cantidad_devuelta'))
            registrar_devolucion_logic(g.user['ingenio_id'], transaccion_id, cantidad_devuelta)
            flash('Devolución registrada exitosamente. El inventario ha sido ajustado.', 'success')
            return redirect(url_for('main.historial'))
        except ValueError as e:
            flash(f'Error al registrar la devolución: {e}', 'danger')
    return render_template('devolucion.html', transaccion=transaccion_original)

@transactions_bp.route('/transformar_interno', methods=['GET', 'POST'])
@login_required
def transformar_interno():
    if request.method == 'POST':
        try:
            productos_resultantes = []
            for key, value in request.form.items():
                if key.startswith('cantidad_producto_') and float(value) > 0:
                    productos_resultantes.append({"producto_id": int(key.split('_')[-1]), "cantidad": float(value)})
            
            registrar_transformacion_logic(
                g.user['ingenio_id'], int(request.form.get('item_origen_id')), float(request.form.get('cantidad_usada')),
                productos_resultantes, request.form.get('observaciones', '').strip(), int(request.form.get('destino_almacen_id'))
            )
            flash('Transformación registrada exitosamente.', 'success')
            return redirect(url_for('main.historial'))
        except Exception as e:
            flash(f'Error al registrar la transformación: {e}', 'danger')

    lotes_transformables = obtener_lotes_transformables_logic(g.user['ingenio_id'])
    productos = obtener_productos()
    almacenes = obtener_almacenes_por_ingenio_logic(g.user['ingenio_id'])
    productos_derivados = [p for p in productos if p[1] not in ('Arroz semilla', 'Arroz en chala')]
    return render_template('transformar_interno.html', lotes=lotes_transformables, productos_derivados=productos_derivados, almacenes=almacenes)

@transactions_bp.route('/secar_interno', methods=['GET', 'POST'])
@login_required
def secar_lote_interno():
    if request.method == 'POST':
        try:
            secar_lote_logic(g.user['ingenio_id'], int(request.form.get('item_id')), float(request.form.get('cantidad_perdida', 0)), request.form.get('observaciones', '').strip())
            flash('Lote secado y actualizado exitosamente.', 'success')
            return redirect(url_for('main.inventario'))
        except Exception as e:
            flash(f'Error al procesar el secado: {e}', 'danger')
    lotes_secables = obtener_lotes_secables_logic(g.user['ingenio_id'])
    return render_template('secar_lote_interno.html', lotes=lotes_secables)

@transactions_bp.route('/servicio_secado', methods=['GET', 'POST'])
@login_required
def servicio_secado():
    if request.method == 'POST':
        try:
            registrar_servicio_secado_cliente_logic(
                g.user['ingenio_id'], request.form.get('cliente'), int(request.form.get('producto_id')), request.form.get('variedad'),
                float(request.form.get('cantidad_procesada')), request.form.get('unidad'), float(request.form.get('precio_fanega')),
                request.form.get('observaciones'), request.form.get('lote_cliente')
            )
            flash('Servicio de secado para cliente registrado exitosamente.', 'success')
            return redirect(url_for('main.historial'))
        except Exception as e:
            flash(f'Error al registrar el servicio: {e}', 'danger')
    productos = obtener_productos()
    variedades = obtener_variedades_por_ingenio_logic(g.user['ingenio_id'])
    return render_template('servicio_secado.html', productos=productos, variedades=variedades)

@transactions_bp.route('/servicio_pelado', methods=['GET', 'POST'])
@login_required
def servicio_pelado():
    if request.method == 'POST':
        try:
            registrar_servicio_pelado_cliente_logic(
                g.user['ingenio_id'], request.form.get('cliente'), int(request.form.get('producto_id')), request.form.get('variedad'),
                float(request.form.get('cantidad_procesada')), request.form.get('unidad'), float(request.form.get('precio_servicio')),
                request.form.get('observaciones'), request.form.get('lote_cliente')
            )
            flash('Servicio de pelado para cliente registrado exitosamente.', 'success')
            return redirect(url_for('main.historial'))
        except Exception as e:
            flash(f'Error al registrar el servicio: {e}', 'danger')
    productos = obtener_productos()
    productos_pelables = [p for p in productos if p[1] in ('Arroz semilla', 'Arroz en chala')]
    productos_derivados = [p for p in productos if p[1] not in ('Arroz semilla', 'Arroz en chala')]
    variedades = obtener_variedades_por_ingenio_logic(g.user['ingenio_id'])
    return render_template('servicio_pelado.html', productos=productos_pelables, variedades=variedades, productos_derivados=productos_derivados)
