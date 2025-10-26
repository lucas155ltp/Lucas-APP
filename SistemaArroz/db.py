import sqlite3
import hashlib

DB_NAME = 'sistema_arroz.db'

PRODUCTOS = [
    ("Arroz semilla", "SEM", 1),
    ("Arroz 3/4", "T34", 1),
    ("Arroz en chala", "ACH", 1),
    ("Arroz granillo", "GRN", 1),
    ("Arroz blanco", "ARZ", 1),
    ("Afrecho", "AFR", 0),
    ("Colilla", "COL", 1),
    ("Arroz popular", "POP", 1)
]

def crear_tablas():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        # Crear tabla de ingenios
        c.execute('''
            CREATE TABLE IF NOT EXISTS ingenios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                direccion TEXT NOT NULL,
                nit TEXT,
                celular TEXT NOT NULL
            )
        ''')

        # Crear tabla de almacenes
        c.execute('''
            CREATE TABLE IF NOT EXISTS almacenes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                ingenio_id INTEGER NOT NULL,
                FOREIGN KEY (ingenio_id) REFERENCES ingenios(id),
                UNIQUE(nombre, ingenio_id)
            )
        ''')

        # Crear tabla de variedades
        c.execute('''
            CREATE TABLE IF NOT EXISTS variedades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                ingenio_id INTEGER NOT NULL,
                FOREIGN KEY (ingenio_id) REFERENCES ingenios(id),
                UNIQUE(nombre, ingenio_id)
            )
        ''')

        # Crear tabla de usuarios
        c.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                nivel_acceso TEXT NOT NULL CHECK(nivel_acceso IN ('jefe', 'sub-jefe', 'empleado')),
                ingenio_id INTEGER,
                activo INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (ingenio_id) REFERENCES ingenios(id)
            )
        ''')

        # Crear tabla de productos con código
        c.execute('''
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                codigo_producto TEXT NOT NULL UNIQUE,
                requiere_variedad INTEGER NOT NULL DEFAULT 1
            )
        ''')

        # Crear tabla de transacciones
        c.execute('''
            CREATE TABLE IF NOT EXISTS transacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                nombre TEXT NOT NULL,
                fecha TEXT NOT NULL,
                factura_uuid TEXT UNIQUE,
                total REAL NOT NULL,
                observaciones TEXT,
                ingenio_id INTEGER,
                FOREIGN KEY (ingenio_id) REFERENCES ingenios(id)
            )
        ''')

        # Crear tabla de detalle de transacción (con lote)
        c.execute('''
            CREATE TABLE IF NOT EXISTS detalle_transaccion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaccion_id INTEGER NOT NULL,
                producto_id INTEGER NOT NULL,
                variedad TEXT,
                cantidad_kg REAL NOT NULL DEFAULT 0,
                cantidad REAL NOT NULL,
                unidad TEXT NOT NULL,
                precio_unitario REAL NOT NULL,
                subtotal REAL NOT NULL,
                lote TEXT,
                FOREIGN KEY (transaccion_id) REFERENCES transacciones(id),
                FOREIGN KEY (producto_id) REFERENCES productos(id)
            )
        ''')

        # Crear tabla de inventario
        c.execute('''
            CREATE TABLE IF NOT EXISTS inventario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER NOT NULL,
                variedad TEXT,
                lote TEXT,
                cantidad REAL NOT NULL,
                cantidad_kg REAL NOT NULL DEFAULT 0,
                unidad TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'seco' CHECK(estado IN ('mojado', 'seco')),
                fecha_entrada TEXT NOT NULL,
                fecha_salida TEXT,
                precio_venta_unitario REAL,
                ingenio_id INTEGER,
                almacen_id INTEGER,
                FOREIGN KEY (producto_id) REFERENCES productos(id),
                FOREIGN KEY (ingenio_id) REFERENCES ingenios(id),
                FOREIGN KEY (almacen_id) REFERENCES almacenes(id)
            )
        ''')

        # Eliminar tablas antiguas y redundantes si existen
        c.execute('DROP TABLE IF EXISTS lotes')
        c.execute('DROP TABLE IF EXISTS transformaciones')
        c.execute('DROP TABLE IF EXISTS detalle_transformacion')

def poblar_productos():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        for nombre, codigo_producto, requiere_variedad in PRODUCTOS:
            c.execute('SELECT COUNT(*) FROM productos WHERE nombre = ?', (nombre,))
            if c.fetchone()[0] == 0:
                c.execute('INSERT INTO productos (nombre, codigo_producto, requiere_variedad) VALUES (?, ?, ?)', (nombre, codigo_producto, requiere_variedad))

def migrar_esquema():
    # --- Migraciones de Esquema ---
    # Esto asegura que las bases de datos antiguas se actualicen sin perder datos.
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        # --- Migration for 'usuarios' table ---
        try:
            c.execute("PRAGMA table_info(usuarios)")
            columns = [column[1] for column in c.fetchall()]
            if 'username' in columns and 'email' not in columns:
                print("Migrando tabla 'usuarios': renombrando 'username' a 'email'...")
                c.execute("ALTER TABLE usuarios RENAME COLUMN username TO email")
            if 'ingenio_id' not in columns:
                c.execute("ALTER TABLE usuarios ADD COLUMN ingenio_id INTEGER REFERENCES ingenios(id)")
            if 'activo' not in columns:
                c.execute("ALTER TABLE usuarios ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")
        except sqlite3.OperationalError:
            pass # Table might not exist yet.

        # --- Migration for 'inventario' table ---
        try:
            c.execute("PRAGMA table_info(inventario)")
            columns = [column[1] for column in c.fetchall()]
            if 'almacen_id' not in columns:
                print("Migrando tabla 'inventario': añadiendo columna 'almacen_id'...")
                c.execute("ALTER TABLE inventario ADD COLUMN almacen_id INTEGER REFERENCES almacenes(id)")
            if 'estado' not in columns:
                print("Migrando tabla 'inventario': añadiendo columna 'estado'...")
                # Default to 'seco' for existing data to not disrupt peeling operations
                c.execute("ALTER TABLE inventario ADD COLUMN estado TEXT NOT NULL DEFAULT 'seco'")
            if 'precio_venta_unitario' not in columns:
                print("Migrando tabla 'inventario': añadiendo columna 'precio_venta_unitario'...")
                c.execute("ALTER TABLE inventario ADD COLUMN precio_venta_unitario REAL")
        except sqlite3.OperationalError:
            pass # Table might not exist yet.

        # --- Migration for 'cantidad_kg' in 'inventario' table ---
        try:
            c.execute("PRAGMA table_info(inventario)")
            columns = [column[1] for column in c.fetchall()]
            if 'cantidad_kg' not in columns:
                print("Migrando tabla 'inventario': añadiendo columna 'cantidad_kg'...")
                c.execute("ALTER TABLE inventario ADD COLUMN cantidad_kg REAL NOT NULL DEFAULT 0")
                # Poblar la nueva columna basado en datos existentes
                c.execute("UPDATE inventario SET cantidad_kg = cantidad * 46 WHERE unidad = 'quintal'")
                c.execute("UPDATE inventario SET cantidad_kg = cantidad * 200 WHERE unidad = 'fanega'")
                conn.commit()
        except sqlite3.OperationalError:
            pass # Table might not exist yet.
        # --- Migration for other tables ---
        tables_to_migrate = ['transacciones', 'inventario']
        for table in tables_to_migrate:
            try:
                c.execute(f"PRAGMA table_info({table})")
                columns = [column[1] for column in c.fetchall()]
                if 'ingenio_id' not in columns:
                    print(f"Migrando tabla '{table}': añadiendo columna 'ingenio_id'...")
                    c.execute(f"ALTER TABLE {table} ADD COLUMN ingenio_id INTEGER REFERENCES ingenios(id)")
                # Migration for 'factura_uuid' in 'transacciones'
                if table == 'transacciones' and 'factura_uuid' not in columns:
                    # Añadir la columna si no existe.
                    try:
                        c.execute("ALTER TABLE transacciones ADD COLUMN factura_uuid TEXT UNIQUE")
                        print("Migración completada: Se añadió la columna 'factura_uuid' a la tabla 'transacciones'.")
                    except sqlite3.OperationalError as e:
                        print(f"Advertencia al migrar 'transacciones': {e}") # La columna podría existir a pesar de la comprobación
                # Migration for 'observaciones' in 'transacciones'
                if table == 'transacciones' and 'observaciones' not in columns:
                    print("Migrando tabla 'transacciones': añadiendo columna 'observaciones'...")
                    c.execute("ALTER TABLE transacciones ADD COLUMN observaciones TEXT")
            except sqlite3.OperationalError:
                pass # Table might not exist yet.
        
        # --- Migration for 'cantidad_kg' in 'detalle_transaccion' table ---
        try:
            c.execute("PRAGMA table_info(detalle_transaccion)")
            columns = [column[1] for column in c.fetchall()]
            if 'cantidad_kg' not in columns:
                print("Migrando tabla 'detalle_transaccion': añadiendo columna 'cantidad_kg'...")
                c.execute("ALTER TABLE detalle_transaccion ADD COLUMN cantidad_kg REAL NOT NULL DEFAULT 0")
                # No hay una forma fácil de poblar esto retroactivamente, se aplicará a nuevas transacciones.
                conn.commit()
        except sqlite3.OperationalError:
            pass # Table might not exist yet.

        # --- Migration for 'ingenios' table ---
        try:
            c.execute("PRAGMA table_info(ingenios)")
            columns = [column[1] for column in c.fetchall()]
            if 'direccion' not in columns:
                print("Migrando tabla 'ingenios': añadiendo columna 'direccion'...")
                c.execute("ALTER TABLE ingenios ADD COLUMN direccion TEXT NOT NULL")
            if 'nit' not in columns:
                print("Migrando tabla 'ingenios': añadiendo columna 'nit'...")
                c.execute("ALTER TABLE ingenios ADD COLUMN nit TEXT")
            if 'celular' not in columns:
                print("Migrando tabla 'ingenios': añadiendo columna 'celular'...")
                c.execute("ALTER TABLE ingenios ADD COLUMN celular TEXT NOT NULL")
        except sqlite3.OperationalError:
            pass # Table might not exist yet.

def inicializar_db():
    """Crea las tablas, puebla los productos y ejecuta las migraciones."""
    crear_tablas()
    poblar_productos()
    migrar_esquema()

inicializar_db()
def lote_existe(numero_lote: str, ingenio_id: int) -> bool:
    """Verifica si un número de lote ya existe en el inventario de un ingenio."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM inventario WHERE lote = ? AND ingenio_id = ?", (numero_lote, ingenio_id))
        return c.fetchone() is not None

def registrar_compra_transaccion(
    ingenio_id: int, proveedor: str, producto_id: int, variedad: str, cantidad: float, 
    unidad: str, precio: float, total: float, lote: str, fecha: str, almacen_id: int, estado: str, cantidad_kg: float
):
    """
    Registra una transacción de compra completa, incluyendo transacción, detalle,
    e inventario.
    """
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        
        # 1. Registrar transacción principal
        c.execute(
            "INSERT INTO transacciones (tipo, nombre, fecha, total, ingenio_id) VALUES (?, ?, ?, ?, ?)",
            ('compra', proveedor, fecha, total, ingenio_id)
        )
        transaccion_id = c.lastrowid

        # 2. Registrar detalle de la transacción
        c.execute("""
            INSERT INTO detalle_transaccion 
            (transaccion_id, producto_id, variedad, cantidad, cantidad_kg, unidad, precio_unitario, subtotal, lote) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (transaccion_id, producto_id, variedad, cantidad, cantidad_kg, unidad, precio, total, lote))

        # 3. Registrar en el inventario
        c.execute("""
            INSERT INTO inventario (producto_id, variedad, lote, cantidad, cantidad_kg, unidad, fecha_entrada, fecha_salida, precio_venta_unitario, ingenio_id, almacen_id, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?)
        """, (producto_id, variedad, lote, cantidad, cantidad_kg, unidad, fecha, ingenio_id, almacen_id, estado))
        
        conn.commit()
    return lote

# Proceso de transformación (pelado)
def registrar_transformacion_db(
    ingenio_id: int, item_origen_id: int, cantidad_usada: float, productos_resultantes: list, fecha: str, observaciones: str, destino_almacen_id: int
):
    """
    Registra una transformación de un lote de arroz semilla a sus derivados.
    Esta operación es atómica.
    """
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            # 1. Obtener info del lote de origen, verificar stock y estado
            c.execute("SELECT lote, cantidad, cantidad_kg, unidad, producto_id, variedad, estado FROM inventario WHERE id = ? AND ingenio_id = ?", (item_origen_id, ingenio_id))
            item_origen = c.fetchone()
            if not item_origen or item_origen[1] < cantidad_usada:
                raise ValueError("Stock insuficiente en el lote de origen.")
            if item_origen[6] != 'seco': # El índice 6 corresponde al 'estado'
                raise ValueError("Solo se pueden transformar (pelar) lotes con estado 'seco'.")

            lote_origen_str = item_origen[0]
            cantidad_kg_original = item_origen[2]
            unidad_origen = item_origen[3]
            producto_id_origen = item_origen[4]
            variedad_origen = item_origen[5]

            # 2. Actualizar el inventario de origen
            nueva_cantidad_origen = item_origen[1] - cantidad_usada
            nueva_cantidad_kg_origen = nueva_cantidad_origen * (cantidad_kg_original / item_origen[1]) if item_origen[1] > 0 else 0
            c.execute("UPDATE inventario SET cantidad = ?, cantidad_kg = ? WHERE id = ? AND ingenio_id = ?", (nueva_cantidad_origen, nueva_cantidad_kg_origen, item_origen_id, ingenio_id))

            # 3. Crear la transacción principal de 'transformacion'
            total_resultante = sum(p['cantidad'] for p in productos_resultantes)
            c.execute(
                "INSERT INTO transacciones (tipo, nombre, fecha, total, observaciones, ingenio_id) VALUES (?, ?, ?, ?, ?, ?)",
                ('transformacion', f"Desde Lote {lote_origen_str}", fecha, total_resultante, observaciones, ingenio_id)
            )
            transaccion_id = c.lastrowid

            # 4. Registrar el 'consumo' en el detalle de la transacción
            cantidad_kg_usada = cantidad_usada * (cantidad_kg_original / item_origen[1]) if item_origen[1] > 0 else 0
            c.execute("""
                INSERT INTO detalle_transaccion (transaccion_id, producto_id, variedad, cantidad, cantidad_kg, unidad, lote, precio_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (transaccion_id, producto_id_origen, variedad_origen, -cantidad_usada, -cantidad_kg_usada, unidad_origen, lote_origen_str, 0, 0))

            # 5. Registrar los productos resultantes
            for i, prod in enumerate(productos_resultantes):
                nuevo_lote = f"{lote_origen_str}-T{i+1}"
                # Los productos resultantes están en quintales
                KG_POR_QUINTAL = 46
                cantidad_resultante_kg = prod['cantidad'] * KG_POR_QUINTAL
                
                # a. Añadir al inventario
                c.execute("""
                    INSERT INTO inventario (producto_id, variedad, lote, cantidad, cantidad_kg, unidad, fecha_entrada, precio_venta_unitario, ingenio_id, almacen_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """, (
                    prod['producto_id'], variedad_origen, nuevo_lote, prod['cantidad'], cantidad_resultante_kg, 'quintales', fecha, ingenio_id, destino_almacen_id
                ))
                
                # b. Añadir al detalle de la transacción
                c.execute("""
                    INSERT INTO detalle_transaccion (transaccion_id, producto_id, variedad, cantidad, cantidad_kg, unidad, lote, precio_unitario, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (transaccion_id, prod['producto_id'], variedad_origen, prod['cantidad'], cantidad_resultante_kg, 'quintales', nuevo_lote, 0, 0))

            conn.commit()
            return transaccion_id
        except Exception as e:
            conn.rollback()
            raise e

def secar_lote_db(ingenio_id: int, item_id: int, cantidad_perdida_quintales: float, fecha: str, observaciones: str):
    """
    Actualiza el estado de un lote a 'seco', reduce su cantidad y registra la transacción.
    La cantidad perdida se recibe en QUINTALES y se convierte a la unidad del lote si es necesario.
    """
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            # 1. Obtener info del lote de origen, verificar stock y estado
            c.execute("SELECT lote, cantidad, cantidad_kg, unidad, producto_id, variedad, estado FROM inventario WHERE id = ? AND ingenio_id = ?", (item_id, ingenio_id))
            item_origen = c.fetchone()
            if not item_origen:
                raise ValueError("El lote no existe.")
            if item_origen[6] != 'mojado':
                raise ValueError("El lote seleccionado ya está seco.")

            cantidad_original = item_origen[1]
            cantidad_kg_original = item_origen[2]
            unidad_original = item_origen[3]
            lote_origen_str = item_origen[0]

            # 2. Convertir la pérdida de QUINTALES a la unidad del lote
            cantidad_perdida_convertida = 0.0
            if unidad_original == 'quintal':
                
                cantidad_perdida_convertida = cantidad_perdida_quintales  
            elif unidad_original == 'fanega':
                # Convertir la pérdida de quintales a fanegas para la resta
                # 1 fanega = 200 kg, 1 quintal = 46 kg.
                kg_por_quintal = 46
                kg_por_fanega = 200
                cantidad_perdida_convertida = (cantidad_perdida_quintales * kg_por_quintal) / kg_por_fanega
            else:
                raise ValueError(f"No se puede convertir la merma para la unidad '{unidad_original}'. Solo se soporta 'quintal' y 'fanega'.")

            if cantidad_perdida_convertida > cantidad_original:
                raise ValueError("La cantidad perdida no puede ser mayor a la cantidad del lote.")

            # 3. Actualizar el inventario de origen
            nueva_cantidad = cantidad_original - cantidad_perdida_convertida
            nueva_cantidad_kg = nueva_cantidad * (cantidad_kg_original / cantidad_original) if cantidad_original > 0 else 0
            c.execute("UPDATE inventario SET cantidad = ?, cantidad_kg = ?, estado = 'seco' WHERE id = ? AND ingenio_id = ?", (nueva_cantidad, nueva_cantidad_kg, item_id, ingenio_id))

            # 4. Crear la transacción principal de 'secado'
            c.execute(
                "INSERT INTO transacciones (tipo, nombre, fecha, total, observaciones, ingenio_id) VALUES (?, ?, ?, ?, ?, ?)",
                ('secado', f"Lote {lote_origen_str}", fecha, -cantidad_perdida_convertida, observaciones, ingenio_id)
            )
            transaccion_id = c.lastrowid

            # 5. Registrar la merma en el detalle de la transacción
            cantidad_kg_perdida = cantidad_perdida_convertida * (cantidad_kg_original / cantidad_original) if cantidad_original > 0 else 0
            c.execute("""
                INSERT INTO detalle_transaccion (transaccion_id, producto_id, variedad, cantidad, cantidad_kg, unidad, lote, precio_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (transaccion_id, item_origen[4], item_origen[5], -cantidad_perdida_convertida, -cantidad_kg_perdida, unidad_original, lote_origen_str, 0, 0))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

def obtener_transaccion_completa_por_id_db(transaccion_id: int, ingenio_id: int):
    """Obtiene una transacción y su primer detalle, verificando que pertenezca al ingenio."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT 
                t.id, t.tipo, t.nombre, t.fecha, 
                p.nombre, dt.variedad, dt.cantidad, dt.cantidad_kg, dt.unidad, dt.precio_unitario, dt.lote, dt.producto_id
            FROM transacciones t
            JOIN detalle_transaccion dt ON t.id = dt.transaccion_id
            JOIN productos p ON dt.producto_id = p.id
            WHERE t.id = ? AND t.ingenio_id = ?
        """, (transaccion_id, ingenio_id))
        return c.fetchone()

def obtener_detalles_de_venta_db(conn: sqlite3.Connection, transaccion_id: int):
    """Obtiene todos los items (detalles) de una transacción específica."""
    c = conn.cursor()
    c.execute("""
        SELECT
            p.nombre, dt.variedad, dt.cantidad, dt.unidad, dt.precio_unitario, dt.subtotal, dt.lote
        FROM detalle_transaccion dt
        JOIN productos p ON dt.producto_id = p.id
        WHERE dt.transaccion_id = ?
        ORDER BY dt.id
    """, (transaccion_id,))
    return c.fetchall()

def obtener_datos_factura_por_uuid_db(conn: sqlite3.Connection, factura_uuid: str):
    """Obtiene los datos de una factura y su ingenio asociado usando el UUID."""
    c = conn.cursor()
    # Obtener datos principales de la transacción y del ingenio
    c.execute("""
        SELECT t.id, t.nombre, t.fecha, t.total, t.observaciones, i.nombre, i.direccion, i.nit, i.celular, t.tipo
        FROM transacciones t
        JOIN ingenios i ON t.ingenio_id = i.id
        WHERE t.factura_uuid = ? AND t.tipo IN ('venta', 'servicio_secado', 'servicio_pelado')
    """, (factura_uuid,))
    transaccion_info = c.fetchone()

    if not transaccion_info:
        return None

    # Obtener los detalles (items) de la venta o servicio
    detalles = obtener_detalles_de_venta_db(conn, transaccion_info[0])
    return {'info': transaccion_info, 'detalles': detalles}

def obtener_uuid_factura_por_id_db(conn: sqlite3.Connection, transaccion_id: int, ingenio_id: int):
    """Obtiene únicamente el UUID de una factura por su ID de transacción."""
    c = conn.cursor()
    c.execute("SELECT factura_uuid FROM transacciones WHERE id = ? AND ingenio_id = ? AND tipo IN ('venta', 'servicio_secado', 'servicio_pelado')", (transaccion_id, ingenio_id))
    result = c.fetchone()
    return result[0] if result else None

def registrar_devolucion_db(ingenio_id: int, transaccion_origen_id: int, cantidad_devuelta: float, fecha: str):
    """
    Registra una devolución: crea una transacción de 'devolucion' y ajusta el inventario.
    Operación atómica.
    """
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            # 1. Obtener datos de la venta original
            venta_original = obtener_transaccion_completa_por_id_db(transaccion_origen_id, ingenio_id)
            if not venta_original or venta_original[1] != 'venta':
                raise ValueError("La transacción de origen no es una venta válida.")

            _, _, cliente, _, _, variedad, cant_vendida, cant_kg_vendida, unidad, precio_unit, lote, prod_id = venta_original

            if cantidad_devuelta > cant_vendida:
                raise ValueError(f"No se puede devolver más de la cantidad vendida ({cant_vendida} {unidad}).")

            # 2. Calcular el total de la devolución (será negativo)
            total_devolucion = -1 * round(cantidad_devuelta * precio_unit, 2)

            # 3. Crear la nueva transacción de 'devolucion'
            c.execute(
                "INSERT INTO transacciones (tipo, nombre, fecha, total, observaciones, ingenio_id) VALUES (?, ?, ?, ?, ?, ?)",
                ('devolucion', cliente, fecha, total_devolucion, f"Devolución de venta ID {transaccion_origen_id}", ingenio_id)
            )
            nueva_transaccion_id = c.lastrowid

            # Calcular la cantidad en kg devuelta
            cantidad_kg_devuelta = cantidad_devuelta * (cant_kg_vendida / cant_vendida) if cant_vendida > 0 else 0

            # 4. Crear el detalle para la transacción de devolución
            c.execute("""
                INSERT INTO detalle_transaccion (transaccion_id, producto_id, variedad, cantidad, cantidad_kg, unidad, precio_unitario, subtotal, lote)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nueva_transaccion_id, prod_id, variedad, cantidad_devuelta, cantidad_kg_devuelta, unidad, precio_unit, total_devolucion, lote))

            # 5. Ajustar el inventario: sumar la cantidad devuelta al lote correspondiente
            c.execute(
                "UPDATE inventario SET cantidad = cantidad + ?, cantidad_kg = cantidad_kg + ? WHERE lote = ? AND producto_id = ? AND ingenio_id = ?",
                (cantidad_devuelta, cantidad_kg_devuelta, lote, prod_id, ingenio_id)
            )

            # Verificar si la actualización afectó alguna fila. Si no, el lote no se encontró.
            if c.rowcount == 0:
                raise ValueError(f"No se encontró el lote '{lote}' en el inventario para ajustar el stock. La devolución no se pudo completar.")

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise e

def registrar_servicio_cliente_db(ingenio_id: int, tipo: str, cliente: str, total_ingreso: float, fecha: str, observaciones: str, detalles: list, factura_uuid: str = None):
    """
    Registra una transacción de servicio a un cliente (secado, pelado, etc.).
    Esta operación NO afecta al inventario.
    """
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            # 1. Crear la transacción principal
            if factura_uuid:
                c.execute(
                    "INSERT INTO transacciones (tipo, nombre, fecha, total, observaciones, ingenio_id, factura_uuid) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (tipo, cliente, fecha, total_ingreso, observaciones, ingenio_id, factura_uuid)
                )
            else:
                c.execute(
                    "INSERT INTO transacciones (tipo, nombre, fecha, total, observaciones, ingenio_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (tipo, cliente, fecha, total_ingreso, observaciones, ingenio_id)
                )
            transaccion_id = c.lastrowid

            # 2. Registrar los detalles
            for detalle in detalles:
                # Los servicios no manejan KG internamente, así que pasamos 0
                c.execute("""
                    INSERT INTO detalle_transaccion (transaccion_id, producto_id, variedad, cantidad, cantidad_kg, unidad, precio_unitario, subtotal, lote)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    transaccion_id,
                    detalle.get('producto_id'),
                    detalle.get('variedad'),
                    detalle.get('cantidad'), 0, # cantidad_kg es 0 para servicios
                    detalle.get('unidad'),
                    detalle.get('precio_unitario', 0), # Precio del servicio
                    detalle.get('subtotal', 0), # Ingreso por este item
                    detalle.get('lote', None) # Lote del cliente
                ))
            conn.commit()
            return transaccion_id
        except Exception as e:
            conn.rollback()
            raise e

def cambiar_password_db(user_id: int, new_password_hash: str):
    """Actualiza el hash de la contraseña para un usuario específico."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (new_password_hash, user_id))
        conn.commit()

def crear_ingenio_db(nombre: str, direccion: str = "", nit: str = None, celular: str = ""):
    """Crea un nuevo ingenio en la base de datos."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO ingenios (nombre, direccion, nit, celular) VALUES (?, ?, ?, ?)", (nombre, direccion, nit, celular))
        conn.commit()

def crear_almacen_db(nombre: str, ingenio_id: int):
    """Crea un nuevo almacén para un ingenio."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO almacenes (nombre, ingenio_id) VALUES (?, ?)", (nombre, ingenio_id))
        conn.commit()

def crear_variedad_db(nombre: str, ingenio_id: int):
    """Crea una nueva variedad para un ingenio."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO variedades (nombre, ingenio_id) VALUES (?, ?)", (nombre, ingenio_id))
        conn.commit()

def obtener_variedades_db(ingenio_id: int):
    """Obtiene todas las variedades de un ingenio."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        return c.execute("SELECT id, nombre FROM variedades WHERE ingenio_id = ? ORDER BY nombre", (ingenio_id,)).fetchall()

def obtener_almacenes_db(ingenio_id: int):
    """Obtiene todos los almacenes de un ingenio."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        return c.execute("SELECT id, nombre FROM almacenes WHERE ingenio_id = ? ORDER BY nombre", (ingenio_id,)).fetchall()

def obtener_ingenios_db():
    """Obtiene la lista de todos los ingenios de la base de datos."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        return c.execute("SELECT id, nombre, direccion, nit, celular FROM ingenios ORDER BY nombre").fetchall()

def obtener_ingenio_por_id_db(ingenio_id: int):
    """Obtiene los detalles de un ingenio específico por su ID."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        return c.execute("SELECT id, nombre, direccion, nit, celular FROM ingenios WHERE id = ?", (ingenio_id,)).fetchone()

def actualizar_ingenio_db(ingenio_id: int, nombre: str, direccion: str, nit: str = None, celular: str = ""):
    """Actualiza los detalles de un ingenio."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE ingenios SET nombre = ?, direccion = ?, nit = ?, celular = ? WHERE id = ?", (nombre, direccion, nit, celular, ingenio_id))
        conn.commit()

def registrar_ingenio_y_jefe_db(nombre_ingenio: str, email_jefe: str, password_hash: str, direccion: str, nit: str = None, celular: str = ""):
    """Crea un nuevo ingenio y su primer usuario 'jefe' de forma atómica."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        try:
            # 1. Crear el ingenio
            c.execute("INSERT INTO ingenios (nombre, direccion, nit, celular) VALUES (?, ?, ?, ?)", (nombre_ingenio, direccion, nit, celular))
            ingenio_id = c.lastrowid

            # 2. Crear el usuario 'jefe'
            c.execute(
                """INSERT INTO usuarios (email, password_hash, nivel_acceso, ingenio_id, activo)
                   VALUES (?, ?, 'jefe', ?, 1)""",
                (email_jefe, password_hash, ingenio_id)
            )
            conn.commit()
            return ingenio_id
        except sqlite3.IntegrityError as e:
            conn.rollback()
            if "ingenios.nombre" in str(e):
                raise ValueError(f"El ingenio '{nombre_ingenio}' ya existe.")
            if "usuarios.email" in str(e):
                raise ValueError(f"El email '{email_jefe}' ya está registrado.")
            raise e

def obtener_estadisticas_db(ingenio_id: int, fecha_inicio: str, fecha_fin: str, agrupar_por: str = 'dia'):
    """
    Obtiene un conjunto de estadísticas clave para el dashboard de un ingenio de forma optimizada.
    """
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        stats = {}

        # 1. Consulta Única para Totales de Transacciones
        c.execute("""
            SELECT
                SUM(CASE WHEN tipo = 'venta' THEN total ELSE 0 END) as total_ventas,
                SUM(CASE WHEN tipo = 'compra' THEN total ELSE 0 END) as total_compras,
                SUM(CASE WHEN tipo IN ('servicio_secado', 'servicio_pelado') THEN total ELSE 0 END) as total_servicios
            FROM transacciones
            WHERE ingenio_id = ? AND date(fecha) BETWEEN ? AND ?
        """, (ingenio_id, fecha_inicio, fecha_fin))
        
        totales = c.fetchone()
        stats['total_ventas'] = totales[0] or 0.0
        stats['total_compras'] = totales[1] or 0.0
        stats['total_servicios'] = totales[2] or 0.0

        # 2. Consulta para Ventas Agrupadas (Gráfico)
        if agrupar_por == 'mes':
            group_format = "strftime('%Y-%m', fecha)"
        else:  # 'dia'
            group_format = "date(fecha)"

        c.execute("""
            SELECT {group_format} as periodo, SUM(total)
            FROM transacciones
            WHERE ingenio_id = ? AND tipo = 'venta' AND date(fecha) BETWEEN ? AND ?
            GROUP BY periodo
            ORDER BY periodo ASC
        """.format(group_format=group_format), (ingenio_id, fecha_inicio, fecha_fin))
        stats['ventas_agrupadas'] = c.fetchall()

        # 3. Consulta para Métricas de Inventario (Lotes Activos y Valor)
        c.execute("SELECT COUNT(id) FROM inventario WHERE ingenio_id = ? AND cantidad > 0", (ingenio_id,))
        stats['lotes_activos'] = c.fetchone()[0] or 0

        # 4. Consulta Optimizada para Valor de Inventario
        c.execute("""
            SELECT SUM(i.cantidad * COALESCE(dt.precio_unitario, 0) /
                    CASE
                        WHEN i.unidad = dt.unidad THEN 1.0
                        WHEN i.unidad = 'quintal' AND dt.unidad = 'fanega' THEN 4.3478 -- 200kg/46kg = 4.3478
                        WHEN i.unidad = 'fanega' AND dt.unidad = 'quintal' THEN 0.23 -- 46kg/200kg = 0.23
                        ELSE 1.0
                    END)
            FROM inventario i
            LEFT JOIN (
                SELECT dt_inner.lote, dt_inner.precio_unitario, dt_inner.unidad
                FROM detalle_transaccion dt_inner
                JOIN transacciones t_inner ON dt_inner.transaccion_id = t_inner.id
                WHERE t_inner.tipo = 'compra' AND t_inner.ingenio_id = ?
            ) dt ON (SUBSTR(i.lote, 1, INSTR(i.lote || '-T', '-T') - 1)) = dt.lote
            WHERE i.ingenio_id = ? AND i.cantidad > 0
        """, (ingenio_id, ingenio_id))
        
        stats['valor_inventario'] = c.fetchone()[0] or 0.0

        # 5. Distribución del valor del inventario por producto (para gráfico de pastel)
        c.execute("""
            SELECT
                p.nombre,
                SUM(i.cantidad * COALESCE(dt.precio_unitario, 0) /
                    CASE
                        WHEN i.unidad = dt.unidad THEN 1.0
                        WHEN i.unidad = 'quintal' AND dt.unidad = 'fanega' THEN 4.3478
                        WHEN i.unidad = 'fanega' AND dt.unidad = 'quintal' THEN 0.23
                        ELSE 1.0
                    END) as valor_total
            FROM inventario i
            JOIN productos p ON i.producto_id = p.id
            LEFT JOIN (
                SELECT dt_inner.lote, dt_inner.precio_unitario, dt_inner.unidad
                FROM detalle_transaccion dt_inner
                JOIN transacciones t_inner ON dt_inner.transaccion_id = t_inner.id
                WHERE t_inner.tipo = 'compra' AND t_inner.ingenio_id = ?
            ) dt ON (SUBSTR(i.lote, 1, INSTR(i.lote || '-T', '-T') - 1)) = dt.lote
            WHERE i.ingenio_id = ? AND i.cantidad > 0
            GROUP BY p.nombre HAVING valor_total > 0 ORDER BY valor_total DESC
        """, (ingenio_id, ingenio_id))
        stats['inventario_por_producto'] = c.fetchall()

        return stats
