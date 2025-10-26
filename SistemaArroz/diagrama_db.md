# Diagrama de la Base de Datos - Sistema Arroz

Este documento contiene el diagrama de clases de la base de datos en formato Mermaid.
Puedes visualizarlo usando una extensión de Markdown compatible con Mermaid en tu editor (como en VS Code) o pegando el código en un editor en línea como [Mermaid Live](https://mermaid.live).

```mermaid
classDiagram
    direction LR

    class Ingenio {
        +int id
        +string nombre
    }

    class Almacen {
        +int id
        +string nombre
        +int ingenio_id
    }

    class Variedad {
        +int id
        +string nombre
        +int ingenio_id
    }

    class Usuario {
        +int id
        +string email
        +string password_hash
        +string nivel_acceso
        +int ingenio_id
        +bool activo
    }

    class Producto {
        +int id
        +string nombre
        +string codigo_producto
        +bool requiere_variedad
    }

    class Transaccion {
        +int id
        +string tipo
        +string nombre
        +datetime fecha
        +string factura_uuid
        +float total
        +string observaciones
        +int ingenio_id
    }

    class DetalleTransaccion {
        +int id
        +int transaccion_id
        +int producto_id
        +string variedad
        +float cantidad
        +string unidad
        +float precio_unitario
        +float subtotal
        +string lote
    }

    class Inventario {
        +int id
        +int producto_id
        +string variedad
        +string lote
        +float cantidad
        +string unidad
        +string estado
        +datetime fecha_entrada
        +float precio_venta_unitario
        +int ingenio_id
        +int almacen_id
    }

    %% Relaciones con Ingenio
    Ingenio "1" -- "0..*" Usuario : gestiona
    Ingenio "1" -- "0..*" Almacen : posee
    Ingenio "1" -- "0..*" Variedad : define
    Ingenio "1" -- "0..*" Transaccion : registra
    Ingenio "1" -- "0..*" Inventario : contiene

    %% Relaciones de Transacciones
    Transaccion "1" -- "1..*" DetalleTransaccion : tiene
    Producto "1" -- "0..*" DetalleTransaccion : es parte de

    %% Relaciones de Inventario
    Producto "1" -- "0..*" Inventario : se almacena como
    Almacen "1" -- "0..*" Inventario : guarda

    %% Relaciones Lógicas (no por FK directa, pero conceptual)
    DetalleTransaccion ..> Inventario : afecta

```

### Explicación de las Relaciones

*   **`Ingenio`**: Es la entidad central. Un ingenio tiene múltiples `Usuarios`, `Almacenes`, `Variedades`, `Transacciones` e `Inventario`.
*   **`Transaccion`**: Representa cualquier operación (compra, venta, etc.). Cada transacción tiene uno o más `DetalleTransaccion`.
*   **`DetalleTransaccion`**: Contiene los ítems específicos de una transacción, como qué `Producto` se movió, la cantidad y el precio.
*   **`Inventario`**: Representa el stock físico. Cada entrada en el inventario corresponde a un `Producto` y está ubicada en un `Almacen`.
*   **`DetalleTransaccion ..> Inventario`**: La línea punteada indica una relación lógica. Una transacción (a través de sus detalles) *afecta* al inventario (aumentando o disminuyendo el stock), aunque no haya una clave foránea directa entre estas dos tablas.
