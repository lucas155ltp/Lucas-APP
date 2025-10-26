import sqlite3
conn = sqlite3.connect('sistema_arroz.db')
c = conn.cursor()
c.execute('SELECT tipo, factura_uuid FROM transacciones WHERE tipo IN ("venta", "servicio_secado", "servicio_pelado") LIMIT 10')
results = c.fetchall()
print('Transaction types and UUIDs:')
for tipo, uuid in results:
    print(f'{tipo}: {uuid}')
conn.close()
