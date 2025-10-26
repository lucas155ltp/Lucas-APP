import sqlite3
from db import obtener_datos_factura_por_uuid_db, obtener_uuid_factura_por_id_db

# Test obtener_datos_factura_por_uuid_db
print('Testing obtener_datos_factura_por_uuid_db:')
# Test with a non-existent UUID
result = obtener_datos_factura_por_uuid_db(sqlite3.connect('sistema_arroz.db'), 'non-existent-uuid')
print(f'Non-existent UUID: {result}')

# Test with a 'venta' transaction (assuming one exists)
conn = sqlite3.connect('sistema_arroz.db')
c = conn.cursor()
c.execute("SELECT factura_uuid FROM transacciones WHERE tipo = 'venta' LIMIT 1")
venta_uuid = c.fetchone()
if venta_uuid:
    result = obtener_datos_factura_por_uuid_db(conn, venta_uuid[0])
    print(f'Venta UUID: {result is not None}')
else:
    print('No venta transaction found')

# Test with 'servicio_secado' (assuming one exists)
c.execute("SELECT factura_uuid FROM transacciones WHERE tipo = 'servicio_secado' LIMIT 1")
servicio_uuid = c.fetchone()
if servicio_uuid:
    result = obtener_datos_factura_por_uuid_db(conn, servicio_uuid[0])
    print(f'Servicio Secado UUID: {result is not None}')
else:
    print('No servicio_secado transaction found')

# Test with 'servicio_pelado' (assuming one exists)
c.execute("SELECT factura_uuid FROM transacciones WHERE tipo = 'servicio_pelado' LIMIT 1")
pelado_uuid = c.fetchone()
if pelado_uuid:
    result = obtener_datos_factura_por_uuid_db(conn, pelado_uuid[0])
    print(f'Servicio Pelado UUID: {result is not None}')
else:
    print('No servicio_pelado transaction found')

# Test with other type (e.g., 'compra')
c.execute("SELECT factura_uuid FROM transacciones WHERE tipo = 'compra' LIMIT 1")
compra_uuid = c.fetchone()
if compra_uuid and compra_uuid[0]:
    result = obtener_datos_factura_por_uuid_db(conn, compra_uuid[0])
    print(f'Compra UUID: {result}')
else:
    print('No compra transaction with UUID found')

conn.close()

print('\nTesting obtener_uuid_factura_por_id_db:')
# Test obtener_uuid_factura_por_id_db
conn = sqlite3.connect('sistema_arroz.db')
c = conn.cursor()

# Get a venta transaction ID
c.execute("SELECT id, ingenio_id FROM transacciones WHERE tipo = 'venta' LIMIT 1")
venta_row = c.fetchone()
if venta_row:
    result = obtener_uuid_factura_por_id_db(conn, venta_row[0], venta_row[1])
    print(f'Venta ID: {result is not None}')
else:
    print('No venta transaction found')

# Get a servicio_secado transaction ID
c.execute("SELECT id, ingenio_id FROM transacciones WHERE tipo = 'servicio_secado' LIMIT 1")
secado_row = c.fetchone()
if secado_row:
    result = obtener_uuid_factura_por_id_db(conn, secado_row[0], secado_row[1])
    print(f'Servicio Secado ID: {result is not None}')
else:
    print('No servicio_secado transaction found')

# Get a servicio_pelado transaction ID
c.execute("SELECT id, ingenio_id FROM transacciones WHERE tipo = 'servicio_pelado' LIMIT 1")
pelado_row = c.fetchone()
if pelado_row:
    result = obtener_uuid_factura_por_id_db(conn, pelado_row[0], pelado_row[1])
    print(f'Servicio Pelado ID: {result is not None}')
else:
    print('No servicio_pelado transaction found')

# Get a compra transaction ID (should return None)
c.execute("SELECT id, ingenio_id FROM transacciones WHERE tipo = 'compra' LIMIT 1")
compra_row = c.fetchone()
if compra_row:
    result = obtener_uuid_factura_por_id_db(conn, compra_row[0], compra_row[1])
    print(f'Compra ID: {result}')
else:
    print('No compra transaction found')

conn.close()
