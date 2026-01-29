# Comparador de Presupuestos - Aplicación Streamlit

Aplicación web para comparar presupuestos por proyecto y escenario, diseñada específicamente para proyectos solares. Permite gestionar múltiples proyectos con escenarios, calcular IVA desglosado, aplicar AIU configurable, y comparar escenarios lado a lado.

## Características

- **CRUD de Proyectos y Escenarios**: Crear, editar, duplicar y borrar proyectos y escenarios
- **Gestión de Ítems**: Tabla editable tipo Excel con categorías, cantidades, precios, unidades
- **IVA Desglosado**: Cálculo automático de IVA por ítem, con opción de precios que incluyen/excluyen IVA
- **Cálculo AIU**: Configuración flexible de AIU (Administración, Imprevistos, Utilidad) con diferentes reglas de base
- **Ítems Porcentuales**: Soporte para ítems calculados como porcentaje de subtotales o base AIU
- **Comparación**: Comparar dos escenarios mostrando diferencias absolutas y porcentuales
- **Persistencia Local**: Almacenamiento en archivos JSON sin necesidad de base de datos

## Instalación

### Requisitos

- Python 3.8 o superior

### Pasos

1. Crear entorno virtual (recomendado):

```bash
python -m venv .venv
```

2. Activar entorno virtual:

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Ejecutar la aplicación:

```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador en `http://localhost:8501`

## Estructura del Proyecto

```
.
├── app.py                 # Aplicación principal Streamlit
├── budget_model.py        # Modelos de datos y lógica de cálculo
├── storage.py             # Persistencia en JSON
├── formatting.py          # Funciones de formateo (COP, porcentajes)
├── seed_template.py       # Plantilla inicial con datos de ejemplo
├── requirements.txt       # Dependencias Python
├── README.md             # Este archivo
└── data/                 # Carpeta de persistencia (se crea automáticamente)
    ├── projects_index.json
    └── {project_id}.json
```

## Uso

### Crear un Proyecto

1. En el panel lateral, haz clic en "➕ Nuevo Proyecto"
2. Ingresa el nombre del proyecto
3. El proyecto se crea automáticamente

### Crear un Escenario

1. Selecciona un proyecto
2. Haz clic en "➕ Nuevo" en la sección de escenarios
3. Ingresa el nombre del escenario
4. Opcionalmente, marca "Usar plantilla base" para cargar datos de ejemplo

### Editar Ítems

1. Selecciona un proyecto y escenario
2. En la pestaña "📝 Editar Escenario", edita directamente en la tabla
3. Los cálculos se actualizan automáticamente
4. Haz clic en "💾 Guardar Cambios" en el panel lateral para persistir

### Configurar AIU

1. En el panel lateral, marca "Habilitar AIU"
2. Configura los porcentajes de Administración, Imprevistos y Utilidad
3. Selecciona la regla base:
   - **Direct costs (CAPEX+OPEX) excl. VAT**: Todos los costos directos sin IVA
   - **Direct costs excl. client-provided items**: Costos directos excluyendo ítems proporcionados por cliente
   - **Only services/labor**: Solo servicios/labor, excluyendo categorías de equipos

### Comparar Escenarios

1. Ve a la pestaña "⚖️ Comparar"
2. Selecciona Proyecto A + Escenario A
3. Selecciona Proyecto B + Escenario B
4. Revisa las comparaciones de totales, por categoría y por ítem
5. Exporta a CSV si lo necesitas

## Formato de Datos

- **Moneda**: COP con separador de miles (ej: 3.800.000)
- **Cantidades**: Hasta 3 decimales cuando aplique
- **Porcentajes**: 1 decimal (ej: 19,0%)

## Notas Técnicas

- Los datos se guardan localmente en archivos JSON en la carpeta `data/`
- Cada proyecto tiene su propio archivo JSON
- El índice de proyectos se mantiene en `data/projects_index.json`
- Los IDs se generan automáticamente usando UUID4
- Los cambios se guardan explícitamente con el botón "Guardar Cambios"

## Solución de Problemas

### Streamlit no está instalado

Asegúrate de haber activado el entorno virtual y ejecutado:
```bash
pip install -r requirements.txt
```

### Error al cargar proyectos

Si hay un error de JSON corrupto, puedes eliminar manualmente los archivos en `data/` y empezar de nuevo. La aplicación creará nuevos archivos automáticamente.

### Los cambios no se guardan

Asegúrate de hacer clic en "💾 Guardar Cambios" en el panel lateral después de editar.

## Deployment en Streamlit Cloud

### Publicar en Streamlit Cloud

1. **Conectar repositorio:**
   - Ve a [share.streamlit.io](https://share.streamlit.io)
   - Haz clic en "New app"
   - Conecta tu repositorio de GitHub: `alevaconsultores4-star/DelphiCAPEX`
   - Archivo principal: `app.py`
   - Branch: `main` (o `master`)

2. **Configurar variables de entorno:**
   - En la configuración de la app en Streamlit Cloud
   - Agrega la variable: `GEMINI_API_KEY` con tu API key de Google Gemini
   - Esto habilita el análisis IA de diferencias CAPEX

3. **Desplegar:**
   - Haz clic en "Deploy"
   - Streamlit Cloud detectará automáticamente `requirements.txt` e instalará las dependencias

### Notas para Streamlit Cloud

- La carpeta `data/` se creará automáticamente en el servidor
- Los datos se guardan en el servidor de Streamlit Cloud (no se persisten entre reinicios a menos que uses almacenamiento externo)
- La variable `GEMINI_API_KEY` es opcional; sin ella, el análisis IA mostrará un mensaje informativo

## Autenticación local (PoC)

La aplicación soporta autenticación local basada en un fichero `data/users.json`. Para entornos internos o de prueba se usa bcrypt para hashear contraseñas.

- Para crear un administrador inicial localmente, ejecuta la app y usa el botón **Crear admin local (delphi@delphi.local)** en la pantalla de login, o ejecuta desde un REPL:

```python
import auth
auth.seed_admin(email="delphi@delphi.local", password="ChangeMe123!")
```

Recuerda cambiar la contraseña del administrador tras el primer inicio de sesión. Para producción se recomienda migrar a un proveedor de identidad (Supabase/Auth0) y habilitar MFA.

## Licencia

Este proyecto es de uso interno.
