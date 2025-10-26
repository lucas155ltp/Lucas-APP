import sqlite3
from datetime import datetime
import uuid
import hashlib
from db import (
    lote_existe as lote_existe_db,
    registrar_compra_transaccion, 
    cambiar_password_db,
    secar_lote_db,
    registrar_transformacion_db,
    DB_NAME,
    crear_almacen_db,
    obtener_almacenes_db,
    crear_ingenio_db,
    registrar_ingenio_y_jefe_db,
    crear_variedad_db,
    registrar_servicio_cliente_db,
    obtener_variedades_db,
    obtener_ingenios_db,
    obtener_estadisticas_db,
    obtener_transaccion_completa_por_id_db,
    registrar_devolucion_db,
    obtener_detalles_de_venta_db,
    obtener_datos_factura_por_uuid_db,
    obtener_uuid_factura_por_id_db,
)

def obtener_productos():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, nombre, requiere_variedad FROM productos")
        return c.fetchall()

def lote_existe_logic(numero_lote: str, ingenio_id: int) -> bool:
    """Verifica si un lote existe."""
    return lote_existe_db(numero_lote, ingenio_id)

def generar_lote_unico_logic(ingenio_id: int) -> str:
    """Genera un número de lote único para un ingenio."""
    # Formato base: LOTE-AAMMDD-HHMMSS
    base_lote = datetime.now().strftime("LOTE-%y%m%d-%H%M%S")
    lote_candidato = base_lote
    counter = 1
    while lote_existe_logic(lote_candidato, ingenio_id):
        lote_candidato = f"{base_lote}-{counter}"
        counter += 1
    return lote_candidato

def registrar_compra_completa_logic(
    ingenio_id: int, proveedor: str, producto_id: int, variedad: str, cantidad: float, 
    unidad: str, precio: float, lote: str, almacen_id: int, estado: str
):
    """Lógica unificada para registrar una compra completa."""
    if not proveedor:
        raise ValueError("El proveedor es obligatorio.")
    if not lote:
        raise ValueError("El número de lote es obligatorio.")
    if cantidad <= 0 or precio < 0:
        raise ValueError("Cantidad y precio deben ser números positivos.")
    if not almacen_id:
        raise ValueError("Debe seleccionar un almacén.")
    if estado not in ['mojado', 'seco']:
        raise ValueError("El estado debe ser 'mojado' o 'seco'.")
    
    # --- Lógica de Conversión a KG ---
    KG_POR_QUINTAL = 46
    KG_POR_FANEGA = 200
    cantidad_kg = 0
    if unidad == 'quintal':
        cantidad_kg = cantidad * KG_POR_QUINTAL
    elif unidad == 'fanega':
        cantidad_kg = cantidad * KG_POR_FANEGA
    else:
        # Asumimos que si no es quintal o fanega, la cantidad es en KG (aunque no debería pasar con la UI actual)
        cantidad_kg = cantidad

    total = round(cantidad * precio, 2)
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    registrar_compra_transaccion(
        ingenio_id, proveedor, producto_id, variedad, cantidad, unidad, precio, total, lote, fecha, almacen_id, estado, cantidad_kg
    )
    return lote

def obtener_inventario_logic(ingenio_id: int, producto_id=None, lote=None, variedad=None, fecha_inicio=None, fecha_fin=None, almacen_id=None):
    """Obtiene registros del inventario, opcionalmente filtrados."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        base_query = """
            SELECT i.id, p.nombre, p.codigo_producto, i.variedad, i.lote, i.cantidad, i.cantidad_kg, i.unidad, i.estado, i.fecha_entrada, i.precio_venta_unitario, a.nombre
            FROM inventario i
            JOIN productos p ON i.producto_id = p.id
            LEFT JOIN almacenes a ON i.almacen_id = a.id
            WHERE i.cantidad_kg > 0.01 AND i.ingenio_id = ?
        """
        params = [ingenio_id]
        conditions = []

        if producto_id:
            conditions.append("i.producto_id = ?")
            params.append(producto_id)
        
        if lote:
            conditions.append("i.lote LIKE ?")
            params.append(f"%{lote}%")

        if variedad:
            conditions.append("i.variedad = ?")
            params.append(variedad)
        
        if fecha_inicio and fecha_fin:
            conditions.append("DATE(i.fecha_entrada) BETWEEN ? AND ?")
            params.append(fecha_inicio)
            params.append(fecha_fin)

        if almacen_id:
            conditions.append("i.almacen_id = ?")
            params.append(almacen_id)

        if conditions:
            base_query += " AND " + " AND ".join(conditions)
            
        base_query += " ORDER BY i.fecha_entrada DESC"
        
        return c.execute(base_query, tuple(params)).fetchall()

def obtener_item_inventario_por_id(ingenio_id: int, item_id: int):
    """Obtiene un item específico del inventario por su ID, verificando que pertenezca al ingenio."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        query = """
            SELECT 
                i.id, p.nombre, i.variedad, i.lote, i.cantidad, i.cantidad_kg, i.unidad, 
                i.producto_id, i.precio_venta_unitario, i.almacen_id, a.nombre,
                dt.precio_unitario AS precio_compra,
                dt.unidad AS unidad_compra
            FROM inventario i
            JOIN productos p ON i.producto_id = p.id
            LEFT JOIN almacenes a ON i.almacen_id = a.id
            LEFT JOIN (
                SELECT 
                    dt_inner.lote, 
                    dt_inner.precio_unitario, 
                    dt_inner.unidad, 
                    t_inner.ingenio_id
                FROM detalle_transaccion dt_inner
                JOIN transacciones t_inner ON dt_inner.transaccion_id = t_inner.id
                WHERE t_inner.tipo = 'compra'
            ) dt ON (CASE WHEN INSTR(i.lote, '-T') > 0 THEN SUBSTR(i.lote, 1, INSTR(i.lote, '-T') - 1) ELSE i.lote END) = dt.lote 
                   AND i.ingenio_id = dt.ingenio_id
            WHERE i.id = ? AND i.ingenio_id = ?
        """
        return c.execute(query, (item_id, ingenio_id)).fetchone()

def registrar_venta_multiproducto_logic(ingenio_id: int, comprador: str, observaciones: str, carrito: dict):
    """Registra una venta de múltiples productos desde el carrito."""
    if not comprador:
        raise ValueError("El nombre del comprador es obligatorio.")
    if not carrito:
        raise ValueError("El carrito está vacío, no se puede registrar la venta.")

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            # 1. Calcular el total y crear la transacción principal
            gran_total = sum(item['cantidad'] * item['precio'] for item in carrito.values())
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            factura_uuid = str(uuid.uuid4())
            c.execute(
                "INSERT INTO transacciones (tipo, nombre, fecha, total, observaciones, ingenio_id, factura_uuid) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ('venta', comprador, fecha, gran_total, observaciones, ingenio_id, factura_uuid)
            )
            transaccion_id = c.lastrowid

            # 2. Iterar sobre el carrito para crear detalles y actualizar inventario
            for item_id_str, item in carrito.items():
                item_id = int(item_id_str)
                cantidad_vendida = item['cantidad']
                subtotal = item['cantidad'] * item['precio']
                
                # Calcular la cantidad en KG vendida
                cantidad_kg_vendida = cantidad_vendida * (item['cantidad_kg_disponible'] / item['stock_disponible']) if item['stock_disponible'] > 0 else 0

                # a. Crear detalle de la transacción
                c.execute("""
                    INSERT INTO detalle_transaccion (transaccion_id, producto_id, variedad, cantidad, cantidad_kg, unidad, precio_unitario, subtotal, lote) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (transaccion_id, item['producto_id'], item['variedad'], cantidad_vendida, cantidad_kg_vendida, item['unidad'], item['precio'], subtotal, item['lote']))

                # b. Actualizar inventario (descontar stock)
                c.execute("UPDATE inventario SET cantidad = cantidad - ? WHERE id = ? AND ingenio_id = ?", (item['cantidad'], item_id, ingenio_id))

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise ValueError(f"Error en la base de datos al procesar la venta: {e}")

def actualizar_precio_venta_logic(ingenio_id: int, item_id: int, nuevo_precio: float):
    """Actualiza el precio de venta para un item específico del inventario."""
    if nuevo_precio < 0:
        raise ValueError("El precio de venta no puede ser negativo.")
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE inventario SET precio_venta_unitario = ? WHERE id = ? AND ingenio_id = ?", (nuevo_precio, item_id, ingenio_id))
        conn.commit()

def obtener_historial_transacciones_logic(ingenio_id: int, tipo=None, producto_id=None, nombre=None, lote=None, fecha_inicio=None, fecha_fin=None):
    """Obtiene el historial de transacciones, opcionalmente filtrado."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        query = """
            SELECT t.id, t.tipo, t.nombre, t.fecha, p.nombre, p.codigo_producto,
                   dt.variedad, dt.cantidad, dt.cantidad_kg, dt.unidad, dt.precio_unitario, dt.subtotal, dt.lote, t.observaciones
            FROM transacciones t
            LEFT JOIN detalle_transaccion dt ON t.id = dt.transaccion_id
            LEFT JOIN productos p ON dt.producto_id = p.id
            WHERE t.ingenio_id = ?
        """
        params = [ingenio_id]
        if tipo:
            query += " AND t.tipo = ?"
            params.append(tipo)
        if producto_id:
            query += " AND dt.producto_id = ?"
            params.append(producto_id)
        if nombre:
            query += " AND t.nombre LIKE ?"
            params.append(f"%{nombre}%")
        if lote:
            query += " AND dt.lote LIKE ?"
            params.append(f"%{lote}%")
        
        if fecha_inicio and fecha_fin:
            query += " AND date(t.fecha) BETWEEN ? AND ?"
            params.append(fecha_inicio)
            params.append(fecha_fin)

        
        query += " ORDER BY t.fecha DESC"
        
        return c.execute(query, tuple(params)).fetchall()

def obtener_transaccion_completa_por_id_logic(transaccion_id: int, ingenio_id: int):
    """Obtiene todos los detalles de una transacción específica."""
    transaccion_data = obtener_transaccion_completa_por_id_db(transaccion_id, ingenio_id)
    if transaccion_data:
        # Convertir la tupla a un diccionario para un uso más fácil en la plantilla
        return {
            'id': transaccion_data[0],
            'tipo': transaccion_data[1],
            'nombre': transaccion_data[2],
            'fecha': transaccion_data[3],
            'producto_nombre': transaccion_data[4],
            'variedad': transaccion_data[5],
            'cantidad': transaccion_data[6],
            'cantidad_kg': transaccion_data[7],
            'unidad': transaccion_data[8],
            'precio_unitario': transaccion_data[9],
            'lote': transaccion_data[10],
            'producto_id': transaccion_data[11]
        }
    return None

def obtener_uuid_factura_por_id_logic(transaccion_id: int, ingenio_id: int):
    """Obtiene el UUID de una factura de forma optimizada."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        resultado = obtener_uuid_factura_por_id_db(conn, transaccion_id, ingenio_id)

        # Si la transacción existe (resultado no es None) pero no tiene UUID (resultado[0] es None),
        # se lo asignamos ahora. Esto da compatibilidad a transacciones antiguas.
        if resultado is not None and resultado[0] is None:
            nuevo_uuid = str(uuid.uuid4())
            c.execute(
                "UPDATE transacciones SET factura_uuid = ? WHERE id = ? AND ingenio_id = ?",
                (nuevo_uuid, transaccion_id, ingenio_id)
            )
            conn.commit()
            print(f"UUID asignado a la transacción antigua {transaccion_id}")
            return nuevo_uuid
        return resultado[0] if resultado is not None else None

def obtener_datos_factura_logic(transaccion_id: int, ingenio_id: int, tipos=('venta',)):
    """Obtiene todos los datos necesarios para generar una factura de una transacción."""
    with sqlite3.connect(DB_NAME) as conn:
        # Obtener datos principales de la transacción
        c = conn.cursor()
        c.execute("SELECT nombre, fecha, total, observaciones, tipo FROM transacciones WHERE id = ? AND ingenio_id = ?", (transaccion_id, ingenio_id))
        transaccion_info = c.fetchone()
        if not transaccion_info or transaccion_info[4] not in tipos:
            return None # No es una transacción válida o no pertenece al ingenio

        # Obtener los detalles (items) de la transacción
        detalles = obtener_detalles_de_venta_db(conn, transaccion_id)

        return {
            'info': transaccion_info,
            'detalles': detalles
        }

def obtener_datos_factura_por_uuid_logic(factura_uuid: str):
    """Obtiene los datos de una factura para la vista pública usando su UUID."""
    with sqlite3.connect(DB_NAME) as conn:
        return obtener_datos_factura_por_uuid_db(conn, factura_uuid)

def obtener_lotes_transformables_logic(ingenio_id: int):
    """Obtiene lotes de 'Arroz Semilla' y 'Arroz en chala' con cantidad > 0 en el inventario."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # Buscamos los IDs de los productos transformables
        c.execute("SELECT id FROM productos WHERE nombre IN ('Arroz semilla', 'Arroz en chala')")
        transformable_ids_rows = c.fetchall()
        if not transformable_ids_rows:
            return []
        
        transformable_ids = tuple(row[0] for row in transformable_ids_rows)
        placeholders = ','.join('?' for _ in transformable_ids)

        query = f"""
            SELECT i.id, i.lote, i.cantidad, i.cantidad_kg, i.unidad, p.nombre, i.variedad, i.almacen_id
            FROM inventario i
            JOIN productos p ON i.producto_id = p.id
            WHERE i.producto_id IN ({placeholders}) AND i.cantidad > 0 AND i.ingenio_id = ? AND i.estado = 'seco'
            ORDER BY i.fecha_entrada ASC
        """
        return c.execute(query, transformable_ids + (ingenio_id,)).fetchall()

def obtener_lotes_secables_logic(ingenio_id: int):
    """Obtiene lotes de 'Arroz Semilla' y 'Arroz en chala' con estado 'mojado'."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM productos WHERE nombre IN ('Arroz semilla', 'Arroz en chala')")
        secable_ids_rows = c.fetchall()
        if not secable_ids_rows:
            return []
        
        secable_ids = tuple(row[0] for row in secable_ids_rows)
        placeholders = ','.join('?' for _ in secable_ids)

        query = f"""
            SELECT i.id, i.lote, i.cantidad, i.unidad, p.nombre, i.variedad, i.almacen_id
            FROM inventario i
            JOIN productos p ON i.producto_id = p.id
            WHERE i.producto_id IN ({placeholders}) AND i.cantidad > 0 AND i.ingenio_id = ? AND i.estado = 'mojado'
            ORDER BY i.fecha_entrada ASC
        """
        return c.execute(query, secable_ids + (ingenio_id,)).fetchall()

def registrar_transformacion_logic(
    ingenio_id: int, item_origen_id: int, cantidad_usada: float, productos_resultantes: list, observaciones: str, destino_almacen_id: int
):
    """
    Valida y registra una transformación de un lote de arroz semilla a sus derivados.
    """
    if cantidad_usada <= 0:
        raise ValueError("La cantidad a transformar debe ser mayor a 0.")
    if not destino_almacen_id:
        raise ValueError("Debe seleccionar un almacén de destino para los productos resultantes.")
    
    if not productos_resultantes:
        raise ValueError("Debe haber al menos un producto resultante.")

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return registrar_transformacion_db(
        ingenio_id, item_origen_id, cantidad_usada, productos_resultantes, fecha, observaciones, destino_almacen_id
    )

def secar_lote_logic(ingenio_id: int, item_id: int, cantidad_perdida_quintales: float, observaciones: str):
    """
    Valida y registra el secado de un lote. La cantidad perdida se recibe en Quintales.
    """
    if cantidad_perdida_quintales < 0:
        raise ValueError("La cantidad perdida no puede ser negativa.")

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    secar_lote_db(ingenio_id, item_id, cantidad_perdida_quintales, fecha, observaciones)

def registrar_devolucion_logic(ingenio_id: int, transaccion_origen_id: int, cantidad_devuelta: float):
    """Valida y registra una devolución."""
    if cantidad_devuelta <= 0:
        raise ValueError("La cantidad a devolver debe ser mayor a cero.")
    
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    registrar_devolucion_db(ingenio_id, transaccion_origen_id, cantidad_devuelta, fecha)

def registrar_servicio_secado_cliente_logic(
    ingenio_id: int, cliente: str, producto_id: int, variedad: str,
    cantidad_procesada: float, unidad: str, precio_por_fanega: float, observaciones: str, lote_cliente: str
):
    """Registra un servicio de secado a un cliente y calcula el ingreso."""
    if not cliente:
        raise ValueError("El nombre del cliente es obligatorio.")
    if cantidad_procesada <= 0 or precio_por_fanega < 0:
        raise ValueError("La cantidad procesada debe ser positiva y el precio no puede ser negativo.")

    # Conversión a fanegas para calcular el ingreso
    # 1 fanega = 200 kg, 1 quintal = 46 kg
    cantidad_en_fanegas = 0
    if unidad == 'fanega':
        cantidad_en_fanegas = cantidad_procesada
    elif unidad == 'quintal':
        kg_por_quintal = 46
        kg_por_fanega = 200
        cantidad_en_fanegas = (cantidad_procesada * kg_por_quintal) / kg_por_fanega
    else:
        raise ValueError(f"Unidad '{unidad}' no soportada para el cálculo de servicio.")

    total_ingreso = round(cantidad_en_fanegas * precio_por_fanega, 2)
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    detalles = [{
        'producto_id': producto_id,
        'variedad': variedad,
        'cantidad': cantidad_en_fanegas,
        'unidad': 'fanega',
        'precio_unitario': precio_por_fanega, # Precio del servicio por fanega
        'subtotal': total_ingreso,
        'lote': lote_cliente
    }]

    transaccion_id = registrar_servicio_cliente_db(ingenio_id, 'servicio_secado', cliente, total_ingreso, fecha, observaciones, detalles)
    return transaccion_id

def registrar_servicio_pelado_cliente_logic(
    ingenio_id: int, cliente: str, producto_id: int, variedad: str,
    cantidad_procesada: float, unidad: str, precio_por_fanega: float, observaciones: str, lote_cliente: str
):
    """Registra un servicio de pelado a un cliente y calcula el ingreso."""
    if not cliente:
        raise ValueError("El nombre del cliente es obligatorio.")
    if cantidad_procesada <= 0 or precio_por_fanega < 0:
        raise ValueError("La cantidad procesada debe ser positiva y el precio no puede ser negativo.")

    # Conversión a fanegas para calcular el ingreso
    # 1 fanega = 200 kg, 1 quintal = 46 kg
    cantidad_en_fanegas = 0
    if unidad == 'fanega':
        cantidad_en_fanegas = cantidad_procesada
    elif unidad == 'quintal':
        kg_por_quintal = 46
        kg_por_fanega = 200
        cantidad_en_fanegas = (cantidad_procesada * kg_por_quintal) / kg_por_fanega
    else:
        raise ValueError(f"Unidad '{unidad}' no soportada para el cálculo de servicio.")

    total_ingreso = round(cantidad_en_fanegas * precio_por_fanega, 2)
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    detalles = [{
        'producto_id': producto_id,
        'variedad': variedad,
        'cantidad': cantidad_en_fanegas,
        'unidad': 'fanega',
        'precio_unitario': precio_por_fanega, # Precio del servicio por fanega
        'subtotal': total_ingreso,
        'lote': lote_cliente
    }]

    # Usamos la misma función de DB, pero con un tipo de transacción diferente
    transaccion_id = registrar_servicio_cliente_db(ingenio_id, 'servicio_pelado', cliente, total_ingreso, fecha, observaciones, detalles)
    return transaccion_id

def _hash_password(password: str) -> str:
    """Genera un hash SHA-256 para la contraseña."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verificar_usuario(email: str, password: str) -> dict | None:
    """Verifica las credenciales del usuario y devuelve sus datos si son correctas."""
    password_hash = _hash_password(password)
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(
            """SELECT u.id, u.email, u.nivel_acceso, u.ingenio_id, i.nombre 
               FROM usuarios u 
               LEFT JOIN ingenios i ON u.ingenio_id = i.id
               WHERE u.email = ? AND u.password_hash = ? AND u.activo = 1""",
            (email, password_hash)
        )
        user_data = c.fetchone()
    if user_data:
        return {
            "id": user_data[0], 
            "email": user_data[1], 
            "nivel_acceso": user_data[2],
            "ingenio_id": user_data[3],
            "ingenio_nombre": user_data[4]
        }
    return None

def crear_usuario_logic(email: str, password: str, nivel_acceso: str, ingenio_id: int):
    """Crea un nuevo usuario en la base de datos."""
    if not email or not password:
        raise ValueError("El email y la contraseña son obligatorios.")
    if nivel_acceso not in ['sub-jefe', 'empleado']:
        raise ValueError("El nivel de acceso debe ser 'sub-jefe' o 'empleado'.")
    if not ingenio_id:
        raise ValueError("No se puede crear un usuario porque tu cuenta de jefe no está asignada a un ingenio.")
    
    password_hash = _hash_password(password)
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO usuarios (email, password_hash, nivel_acceso, ingenio_id, activo) VALUES (?, ?, ?, ?, ?)",
                (email, password_hash, nivel_acceso, ingenio_id, 1)
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: usuarios.email" in str(e):
                raise ValueError(f"El email '{email}' ya está en uso.")
            else:
                # Capturar otros errores de integridad (claves foráneas, etc.)
                raise ValueError(f"Error de integridad en la base de datos: {e}")
        except sqlite3.Error as e:
            # Capturar otros errores de la base de datos (esquema incorrecto, etc.)
            raise ValueError(f"Error en la base de datos al crear el usuario: {e}")

def cambiar_password_logic(user_id: int, old_password: str, new_password: str, confirm_password: str):
    """Valida y cambia la contraseña de un usuario."""
    if not new_password or new_password != confirm_password:
        raise ValueError("Las contraseñas nuevas no coinciden o están vacías.")
    if len(new_password) < 4:
        raise ValueError("La nueva contraseña debe tener al menos 4 caracteres.")

    # Verificar la contraseña antigua obteniendo primero el username
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT email FROM usuarios WHERE id = ?", (user_id,))
        user_row = c.fetchone()
        if not user_row:
            raise ValueError("El usuario no existe.")
        email = user_row[0]
    
    user = verificar_usuario(email, old_password)
    if user is None:
        raise ValueError("La contraseña actual es incorrecta.")

    # Hashear y actualizar la nueva contraseña
    new_password_hash = _hash_password(new_password)
    cambiar_password_db(user_id, new_password_hash)

def crear_ingenio_logic(nombre: str, direccion: str, nit: str = None, celular: str = ""):
    """Crea un nuevo ingenio."""
    if not nombre or not nombre.strip():
        raise ValueError("El nombre del ingenio es obligatorio.")
    if not direccion or not direccion.strip():
        raise ValueError("La dirección del ingenio es obligatoria.")
    if not celular or not celular.strip():
        raise ValueError("El celular del ingenio es obligatorio.")
    try:
        crear_ingenio_db(nombre.strip(), direccion.strip(), nit.strip() if nit else None, celular.strip())
    except sqlite3.IntegrityError:
        raise ValueError(f"El ingenio '{nombre.strip()}' ya existe.")

def crear_almacen_logic(nombre: str, ingenio_id: int):
    """Crea un nuevo almacén."""
    if not nombre or not nombre.strip():
        raise ValueError("El nombre del almacén es obligatorio.")
    if not ingenio_id:
        raise ValueError("El usuario no está asociado a un ingenio.")
    try:
        crear_almacen_db(nombre.strip(), ingenio_id)
    except sqlite3.IntegrityError:
        raise ValueError(f"El almacén '{nombre.strip()}' ya existe en este ingenio.")

def crear_variedad_logic(nombre: str, ingenio_id: int):
    """Crea una nueva variedad."""
    if not nombre or not nombre.strip():
        raise ValueError("El nombre de la variedad es obligatorio.")
    if not ingenio_id:
        raise ValueError("El usuario no está asociado a un ingenio.")
    try:
        crear_variedad_db(nombre.strip(), ingenio_id)
    except sqlite3.IntegrityError:
        raise ValueError(f"La variedad '{nombre.strip()}' ya existe en este ingenio.")

def obtener_variedades_por_ingenio_logic(ingenio_id: int):
    """Obtiene la lista de variedades de un ingenio."""
    if not ingenio_id:
        return []
    return obtener_variedades_db(ingenio_id)

def obtener_almacenes_por_ingenio_logic(ingenio_id: int):
    """Obtiene la lista de almacenes de un ingenio."""
    if not ingenio_id:
        return []
    return obtener_almacenes_db(ingenio_id)
def obtener_ingenios_logic():
    """Obtiene la lista de todos los ingenios."""
    return obtener_ingenios_db()

def actualizar_ingenio_logic(ingenio_id: int, nombre: str, direccion: str, nit: str = None, celular: str = ""):
    """Actualiza los detalles de un ingenio."""
    from db import actualizar_ingenio_db
    actualizar_ingenio_db(ingenio_id, nombre, direccion, nit, celular)

def registrar_nuevo_ingenio_y_jefe_logic(nombre_ingenio: str, email_jefe: str, password: str, direccion: str, nit: str = None, celular: str = ""):
    """Valida y registra un nuevo ingenio y su primer jefe."""
    if not all([nombre_ingenio, email_jefe, password, direccion, celular]):
        raise ValueError("Todos los campos son obligatorios.")
    if "@" not in email_jefe or "." not in email_jefe:
        raise ValueError("El email no es válido.")
    if len(password) < 4:
        raise ValueError("La contraseña debe tener al menos 4 caracteres.")

    password_hash = _hash_password(password)
    try:
        return registrar_ingenio_y_jefe_db(nombre_ingenio, email_jefe, password_hash, direccion, nit, celular)
    except sqlite3.Error as e:
        # Capturar cualquier error de la base de datos y envolverlo en un ValueError
        raise ValueError(f"Error en la base de datos al registrar el ingenio: {e}")

def obtener_usuarios_por_ingenio_logic(ingenio_id: int):
    """Obtiene todos los usuarios de un ingenio específico."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, email, nivel_acceso, activo FROM usuarios WHERE ingenio_id = ?",
            (ingenio_id,)
        )
        return c.fetchall()

def toggle_acceso_usuario_logic(user_id_a_modificar: int, actor_user_id: int):
    """Activa o desactiva un usuario, verificando permisos."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT nivel_acceso, ingenio_id FROM usuarios WHERE id = ?", (actor_user_id,))
        actor = c.fetchone()
        if not actor or actor[0] != 'jefe':
            raise PermissionError("Solo un 'jefe' puede modificar el acceso de usuarios.")
        
        c.execute("SELECT activo, ingenio_id FROM usuarios WHERE id = ?", (user_id_a_modificar,))
        user_a_modificar = c.fetchone()
        if not user_a_modificar or user_a_modificar[1] != actor[1]:
            raise ValueError("El usuario a modificar no existe o no pertenece a su ingenio.")
        if user_id_a_modificar == actor_user_id:
            raise ValueError("Un jefe no puede desactivarse a sí mismo.")
        nuevo_estado = 0 if user_a_modificar[0] == 1 else 1
        c.execute("UPDATE usuarios SET activo = ? WHERE id = ?", (nuevo_estado, user_id_a_modificar))
        conn.commit()

def obtener_estadisticas_dashboard_logic(ingenio_id: int, fecha_inicio: str, fecha_fin: str):
    """Obtiene un diccionario con todas las estadísticas para el dashboard."""
    if not ingenio_id:
        return {}

    from datetime import date, timedelta
    fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
    fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
    dias_en_rango = (fecha_fin_dt - fecha_inicio_dt).days

    # Decidir si agregar por día o por mes
    agrupar_por = 'mes' if dias_en_rango > 31 else 'dia'

    stats_db = obtener_estadisticas_db(ingenio_id, fecha_inicio, fecha_fin, agrupar_por)

    # El balance ahora se calcula directamente en la capa de lógica
    balance = (stats_db.get('total_ventas', 0.0) + stats_db.get('total_servicios', 0.0)) - stats_db.get('total_compras', 0.0)

    # Formatear ventas agrupadas para el gráfico
    if agrupar_por == 'dia':
        ventas_dict = {v[0]: v[1] for v in stats_db.get('ventas_agrupadas', [])} # { '2023-01-01': 100, ... }
        ventas_formateadas = [
            {'fecha': d.strftime('%d %b'), 'total': ventas_dict.get(d.strftime('%Y-%m-%d'), 0)}
            for d in [fecha_inicio_dt + timedelta(days=i) for i in range(dias_en_rango + 1)]
        ]
    else: # Agrupado por mes
        ventas_formateadas = [
            {'fecha': datetime.strptime(v[0], '%Y-%m').strftime('%b %Y'), 'total': v[1]}
            for v in stats_db.get('ventas_agrupadas', [])
        ]

    # Formatear datos para el gráfico de inventario
    inventario_chart_data = {
        'labels': [row[0] for row in stats_db.get('inventario_por_producto', [])],
        'data': [round(row[1], 2) for row in stats_db.get('inventario_por_producto', [])]
    }
    
    return {**stats_db, 'balance': balance, 'ventas_agrupadas': ventas_formateadas, 'agrupacion_grafico': agrupar_por, 'inventario_chart_data': inventario_chart_data}
