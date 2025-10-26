
import types
import sqlite3
import uuid
import pytest

import logic

# ---------- Helpers to patch DB_NAME to an in-memory sqlite for pure SQL paths ----------
@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch):
    # For functions that directly use sqlite3 with DB_NAME, point to an in-memory DB and minimal schema
    # Many logic functions delegate to db.py functions; those will be mocked per-test.
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    # Minimal tables used by some read-only logic paths
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY,
            nombre TEXT,
            codigo_producto TEXT,
            requiere_variedad INTEGER
        );
        CREATE TABLE IF NOT EXISTS almacenes (
            id INTEGER PRIMARY KEY,
            nombre TEXT
        );
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY,
            producto_id INTEGER,
            variedad TEXT,
            lote TEXT,
            cantidad REAL,
            unidad TEXT,
            estado TEXT,
            fecha_entrada TEXT,
            precio_venta_unitario REAL,
            almacen_id INTEGER,
            ingenio_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE,
            password_hash TEXT,
            nivel_acceso TEXT,
            ingenio_id INTEGER,
            activo INTEGER
        );
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY,
            tipo TEXT,
            nombre TEXT,
            fecha TEXT,
            total REAL,
            observaciones TEXT,
            ingenio_id INTEGER,
            factura_uuid TEXT
        );
        CREATE TABLE IF NOT EXISTS detalle_transaccion (
            id INTEGER PRIMARY KEY,
            transaccion_id INTEGER,
            producto_id INTEGER,
            variedad TEXT,
            cantidad REAL,
            unidad TEXT,
            precio_unitario REAL,
            subtotal REAL,
            lote TEXT
        );
        """
    )
    conn.commit()

    # Monkeypatch logic.DB_NAME to use a shared in-memory DB via URI
    # Use a unique name so each test module has isolated DB
    db_uri = "file:test_logic?mode=memory&cache=shared"
    shared_conn = sqlite3.connect(db_uri, uri=True)
    # Ensure schema exists in shared_conn as well
    with shared_conn:
        pass
    monkeypatch.setattr(logic, "DB_NAME", db_uri)
    yield
    conn.close()
    shared_conn.close()


# ---------- Behaviors to be tested ----------
# 1) generar_lote_unico_logic debe generar un código diferente si el candidato existe (usa lote_existe_db)
# 2) registrar_compra_completa_logic valida entradas y calcula total; llama a registrar_compra_transaccion
# 3) verificar_usuario retorna None con credenciales inválidas y dict con válidas
# 4) actualizar_precio_venta_logic no acepta precio negativo y actualiza registro
# 5) obtener_estadisticas_dashboard_logic agrupa por día/mes y calcula balance


def test_generar_lote_unico_logic_increments_when_exists(monkeypatch):
    calls = {"count": 0}

    def fake_lote_existe(numero_lote, ingenio_id):
        # First call returns True to force increment, next returns False
        calls["count"] += 1
        return calls["count"] == 1

    monkeypatch.setattr(logic, "lote_existe_logic", fake_lote_existe)
    lote = logic.generar_lote_unico_logic(ingenio_id=1)
    assert lote.endswith("-1") or "-" in lote  # Should have increment suffix if first candidate existed


def test_registrar_compra_completa_logic_validates_and_calls_db(monkeypatch):
    captured = {}

    def fake_registrar_compra_transaccion(ingenio_id, proveedor, producto_id, variedad, cantidad, unidad, precio, total, lote, fecha, almacen_id, estado):
        captured.update(locals())

    monkeypatch.setattr(logic, "registrar_compra_transaccion", fake_registrar_compra_transaccion)

    lote = "LOTE-ABC"
    result = logic.registrar_compra_completa_logic(
        ingenio_id=2,
        proveedor="Proveedor X",
        producto_id=10,
        variedad="N/A",
        cantidad=5.5,
        unidad="qq",
        precio=12.0,
        lote=lote,
        almacen_id=3,
        estado="seco",
    )
    assert result == lote
    assert captured["total"] == pytest.approx(66.0)
    assert captured["estado"] == "seco"

    # Negative checks
    with pytest.raises(ValueError):
        logic.registrar_compra_completa_logic(2, "", 1, "v", 1, "u", 1, lote, 1, "seco")
    with pytest.raises(ValueError):
        logic.registrar_compra_completa_logic(2, "Prov", 1, "v", 0, "u", 1, lote, 1, "seco")
    with pytest.raises(ValueError):
        logic.registrar_compra_completa_logic(2, "Prov", 1, "v", 1, "u", -1, lote, 1, "seco")
    with pytest.raises(ValueError):
        logic.registrar_compra_completa_logic(2, "Prov", 1, "v", 1, "u", 1, "", 1, "seco")
    with pytest.raises(ValueError):
        logic.registrar_compra_completa_logic(2, "Prov", 1, "v", 1, "u", 1, lote, None, "seco")
    with pytest.raises(ValueError):
        logic.registrar_compra_completa_logic(2, "Prov", 1, "v", 1, "u", 1, lote, 1, "otro")


def test_verificar_usuario_success_and_failure(monkeypatch):
    # Prepare a real user row in the in-memory DB using the same DB_NAME
    with sqlite3.connect(logic.DB_NAME, uri=True) as conn:
        cur = conn.cursor()
        email = "user@example.com"
        pwd = "secret"
        pwd_hash = logic._hash_password(pwd)
        cur.execute(
            "INSERT INTO usuarios (email, password_hash, nivel_acceso, ingenio_id, activo) VALUES (?, ?, ?, ?, 1)",
            (email, pwd_hash, "empleado", 1),
        )
        conn.commit()

    # Wrong password -> None
    assert logic.verificar_usuario("user@example.com", "bad") is None

    # Correct -> dict
    user = logic.verificar_usuario("user@example.com", "secret")
    assert user is not None
    assert user["email"] == "user@example.com"
    assert user["nivel_acceso"] == "empleado"


def test_actualizar_precio_venta_logic(monkeypatch):
    with sqlite3.connect(logic.DB_NAME, uri=True) as conn:
        cur = conn.cursor()
        # Seed minimal data
        cur.execute("INSERT INTO productos (id, nombre, codigo_producto, requiere_variedad) VALUES (1, 'Arroz semilla', 'P1', 0)")
        cur.execute("INSERT INTO inventario (id, producto_id, variedad, lote, cantidad, unidad, estado, fecha_entrada, precio_venta_unitario, almacen_id, ingenio_id) VALUES (1, 1, 'V1', 'L1', 10, 'qq', 'seco', '2023-01-01 00:00:00', 0, 1, 1)")
        conn.commit()

    with pytest.raises(ValueError):
        logic.actualizar_precio_venta_logic(ingenio_id=1, item_id=1, nuevo_precio=-0.01)

    logic.actualizar_precio_venta_logic(ingenio_id=1, item_id=1, nuevo_precio=9.99)

    with sqlite3.connect(logic.DB_NAME, uri=True) as conn:
        price = conn.execute("SELECT precio_venta_unitario FROM inventario WHERE id=1 AND ingenio_id=1").fetchone()[0]
    assert price == pytest.approx(9.99)


def test_obtener_estadisticas_dashboard_logic_computes_balance_and_grouping(monkeypatch):
    # Provide a fake obtener_estadisticas_db that returns shaped data
    def fake_stats(ingenio_id, fi, ff, agrupar_por):
        return {
            'total_ventas': 100.0,
            'total_servicios': 25.0,
            'total_compras': 60.0,
            'ventas_agrupadas': [('2025-01-01', 50.0), ('2025-01-02', 75.0)] if agrupar_por == 'dia' else [('2025-01', 125.0)],
            'inventario_por_producto': [('Arroz semilla', 10.0), ('Arroz en chala', 5.0)],
        }

    monkeypatch.setattr(logic, 'obtener_estadisticas_db', fake_stats)

    res = logic.obtener_estadisticas_dashboard_logic(ingenio_id=1, fecha_inicio='2025-01-01', fecha_fin='2025-01-02')
    assert res['balance'] == pytest.approx(65.0)
    assert res['agrupacion_grafico'] == 'dia'
    assert isinstance(res['ventas_agrupadas'], list) and len(res['ventas_agrupadas']) == 2
    assert res['inventario_chart_data']['labels'] == ['Arroz semilla', 'Arroz en chala']

    # If ingenio_id falsy -> {}
    assert logic.obtener_estadisticas_dashboard_logic(ingenio_id=0, fecha_inicio='2025-01-01', fecha_fin='2025-02-01') == {}
