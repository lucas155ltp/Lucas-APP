import sqlite3
import uuid

conn = sqlite3.connect('sistema_arroz.db')
c = conn.cursor()
c.execute('SELECT id FROM transacciones WHERE tipo IN ("servicio_secado", "servicio_pelado") AND factura_uuid IS NULL')
rows = c.fetchall()
for row in rows:
    new_uuid = str(uuid.uuid4())
    c.execute('UPDATE transacciones SET factura_uuid = ? WHERE id = ?', (new_uuid, row[0]))
    print(f'Assigned UUID {new_uuid} to transaction {row[0]}')
conn.commit()
conn.close()
print('UUIDs assigned to all service transactions')
