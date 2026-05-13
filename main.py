"""
=============================================================
PRICING ANALYTICS ENGINE — API REST (v2.0 con Upload Excel)
=============================================================
Curso: Marketing Analytics: Precios y Promociones
CENTRUM PUCP — Prof. Julio Marchena Ramírez

Endpoints:
  GET  /               → Todos los datos de pricing
  GET  /productos      → Lista de productos con elasticidades
  POST /simular        → Simular cambio de precio
  POST /precio-optimo  → Calcular precio óptimo
  POST /montecarlo     → Simulación Monte Carlo
  POST /comparar       → Comparar múltiples escenarios
  POST /upload         → Subir Excel con datos propios (solo Swagger)
  GET  /docs           → Swagger UI automático

Deploy: Render
  Build: pip install -r requirements.txt
  Start: uvicorn main:app --host 0.0.0.0 --port $PORT
=============================================================
"""

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import numpy as np
import pandas as pd
import io

app = FastAPI(
    title="Pricing Analytics Engine",
    description=(
        "Motor de análisis de pricing con elasticidad, simulación de escenarios y Monte Carlo.\n\n"
        "**¿Cómo cargar tus propios datos?**\n"
        "1. Usa el endpoint /upload para subir tu Excel\n"
        "2. El Excel debe tener las columnas: producto, precio_actual, cantidad_mensual, elasticidad, costo_variable_pct, r2\n"
        "3. Una vez cargado, todos los endpoints trabajarán con TUS datos\n\n"
        "CENTRUM PUCP — Prof. Julio Marchena Ramírez"
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================================================
# BASE DE DATOS DE PRODUCTOS (default, se reemplaza con upload)
# ===========================================================
PRODUCTOS = {
    "Cafe Premium": {
        "precio_actual": 8.37,
        "cantidad_mensual": 1035,
        "elasticidad": -1.4,
        "costo_variable_pct": 0.45,
        "tipo": "Elastico moderado",
        "r2": 0.87
    },
    "Cafe Clasico": {
        "precio_actual": 5.15,
        "cantidad_mensual": 982,
        "elasticidad": -2.5,
        "costo_variable_pct": 0.45,
        "tipo": "Muy elastico",
        "r2": 0.92
    },
    "Te Verde": {
        "precio_actual": 4.62,
        "cantidad_mensual": 1008,
        "elasticidad": -1.8,
        "costo_variable_pct": 0.45,
        "tipo": "Elastico",
        "r2": 0.85
    },
    "Chocolate Caliente": {
        "precio_actual": 6.13,
        "cantidad_mensual": 977,
        "elasticidad": -0.94,
        "costo_variable_pct": 0.45,
        "tipo": "Inelastico",
        "r2": 0.79
    },
    "Jugo Natural": {
        "precio_actual": 7.18,
        "cantidad_mensual": 996,
        "elasticidad": -2.0,
        "costo_variable_pct": 0.45,
        "tipo": "Elastico",
        "r2": 0.88
    },
}

EMPRESA_NOMBRE = "Cafeteria Premium SAC"


# ===========================================================
# MODELOS PYDANTIC
# ===========================================================
class SimularRequest(BaseModel):
    producto: str = Field(..., description="Nombre del producto", example="Cafe Clasico")
    cambio_precio_pct: float = Field(..., description="Porcentaje de cambio: positivo=subir, negativo=bajar", example=-15)

class PrecioOptimoRequest(BaseModel):
    producto: str = Field(..., description="Nombre del producto", example="Cafe Clasico")

class MonteCarloRequest(BaseModel):
    producto: str = Field(..., description="Nombre del producto", example="Cafe Clasico")
    cambio_precio_pct: float = Field(..., description="Cambio de precio a evaluar (%)", example=8)
    n_simulaciones: int = Field(10000, description="Numero de simulaciones", example=10000)
    desviacion_elasticidad: float = Field(0.3, description="Incertidumbre en elasticidad (desv. std)", example=0.3)
    desviacion_costo: float = Field(0.03, description="Incertidumbre en % costo variable (desv. std)", example=0.03)

class CompararRequest(BaseModel):
    producto: str = Field(..., description="Nombre del producto", example="Cafe Clasico")
    escenarios: List[float] = Field(..., description="Lista de cambios de precio (%) a comparar", example=[-20, -10, -5, 0, 5, 10, 15, 20])


# ===========================================================
# FUNCIONES DE CÁLCULO
# ===========================================================
def clasificar_elasticidad(e):
    abs_e = abs(e)
    if abs_e < 1:
        return "Inelastico"
    elif abs_e < 1.5:
        return "Elastico moderado"
    elif abs_e < 2.5:
        return "Elastico"
    else:
        return "Muy elastico"


def calcular_simulacion(producto_nombre: str, cambio_pct: float):
    p = PRODUCTOS[producto_nombre]
    precio_actual = p["precio_actual"]
    cantidad_actual = p["cantidad_mensual"]
    elasticidad = p["elasticidad"]
    cv_pct = p["costo_variable_pct"]

    precio_nuevo = round(precio_actual * (1 + cambio_pct / 100), 2)
    cantidad_nueva = int(cantidad_actual * (precio_nuevo / precio_actual) ** elasticidad)

    cv_actual = round(precio_actual * cv_pct, 2)
    cv_nuevo = round(precio_nuevo * cv_pct, 2)

    ingreso_antes = round(precio_actual * cantidad_actual, 2)
    ingreso_despues = round(precio_nuevo * cantidad_nueva, 2)
    contribucion_antes = round((precio_actual - cv_actual) * cantidad_actual, 2)
    contribucion_despues = round((precio_nuevo - cv_nuevo) * cantidad_nueva, 2)
    delta = round(contribucion_despues - contribucion_antes, 2)

    pct_cantidad = round((cantidad_nueva - cantidad_actual) / cantidad_actual * 100, 1)
    pct_ingreso = round((ingreso_despues - ingreso_antes) / ingreso_antes * 100, 1)
    pct_contribucion = round((contribucion_despues - contribucion_antes) / contribucion_antes * 100, 1)

    conviene = delta > 0

    return {
        "producto": producto_nombre,
        "elasticidad": elasticidad,
        "tipo_elasticidad": p["tipo"],
        "cambio_precio_pct": cambio_pct,
        "precio_actual": precio_actual,
        "precio_nuevo": precio_nuevo,
        "cantidad_actual": cantidad_actual,
        "cantidad_nueva": cantidad_nueva,
        "cambio_cantidad_pct": pct_cantidad,
        "ingreso_antes": ingreso_antes,
        "ingreso_despues": ingreso_despues,
        "cambio_ingreso_pct": pct_ingreso,
        "contribucion_antes": contribucion_antes,
        "contribucion_despues": contribucion_despues,
        "cambio_contribucion_pct": pct_contribucion,
        "impacto_neto": delta,
        "conviene": conviene,
        "recomendacion": f"{'SI conviene' if conviene else 'NO conviene'}: {'gana' if conviene else 'pierde'} S/{abs(delta):,.0f} mensuales en contribucion."
    }


# ===========================================================
# UPLOAD DE EXCEL (solo desde Swagger /docs)
# ===========================================================
@app.post("/upload", summary="Subir Excel con datos propios", tags=["Cargar Datos"])
async def upload_excel(
    archivo: UploadFile = File(
        ...,
        description="Archivo Excel (.xlsx) con columnas: producto, precio_actual, cantidad_mensual, elasticidad, costo_variable_pct, r2"
    )
):
    """
    **Sube tu archivo Excel para trabajar con tus propios datos.**

    El Excel debe tener una hoja con estas columnas exactas:

    | producto | precio_actual | cantidad_mensual | elasticidad | costo_variable_pct | r2 |
    |----------|--------------|-----------------|-------------|-------------------|-----|
    | Aspirina 500mg | 12.50 | 3200 | -0.3 | 0.25 | 0.91 |
    | Vitamina C | 8.90 | 1500 | -1.8 | 0.30 | 0.85 |

    **Notas:**
    - elasticidad: siempre negativa (ej: -1.4)
    - costo_variable_pct: entre 0 y 1 (ej: 0.45 = 45%)
    - r2: entre 0 y 1 (ej: 0.87)
    - Una vez cargado, todos los endpoints usan tus datos
    - Para volver a los datos originales, reinicia la API
    """
    global PRODUCTOS, EMPRESA_NOMBRE

    if not archivo.filename.endswith(('.xlsx', '.xls')):
        return {
            "error": "El archivo debe ser .xlsx o .xls",
            "ayuda": "Descarga la plantilla de ejemplo y úsala como base."
        }

    try:
        contenido = await archivo.read()
        columnas_requeridas = ['producto', 'precio_actual', 'cantidad_mensual', 'elasticidad', 'costo_variable_pct', 'r2']

        # Intentar encontrar la fila del header automáticamente
        # Busca en las primeras 10 filas cuál tiene la columna "producto"
        df = None
        for header_row in range(0, 10):
            try:
                df_test = pd.read_excel(io.BytesIO(contenido), header=header_row)
                cols_test = [str(c).strip().lower() for c in df_test.columns]
                if 'producto' in cols_test:
                    df = df_test
                    break
            except Exception:
                continue

        if df is None:
            return {
                "error": "No se encontró la fila de encabezados con la columna 'producto'",
                "ayuda": "Asegúrate de que tu Excel tenga una fila con estos encabezados: producto, precio_actual, cantidad_mensual, elasticidad, costo_variable_pct, r2"
            }

        columnas_archivo = [str(c).strip().lower() for c in df.columns]
        df.columns = columnas_archivo

        faltantes = [c for c in columnas_requeridas if c not in columnas_archivo]
        if faltantes:
            return {
                "error": f"Faltan columnas: {faltantes}",
                "columnas_encontradas": list(df.columns),
                "columnas_requeridas": columnas_requeridas,
                "ayuda": "Verifica que tu Excel tenga exactamente estas columnas: producto, precio_actual, cantidad_mensual, elasticidad, costo_variable_pct, r2"
            }

        if len(df) == 0:
            return {"error": "El Excel está vacío. Debe tener al menos 1 producto."}

        # Validar datos numéricos
        errores = []
        for i, row in df.iterrows():
            fila = i + 2  # fila real en Excel (header = 1)
            if pd.isna(row['producto']) or str(row['producto']).strip() == '':
                errores.append(f"Fila {fila}: producto vacío")
            if not isinstance(row['precio_actual'], (int, float)) or row['precio_actual'] <= 0:
                errores.append(f"Fila {fila}: precio_actual debe ser positivo")
            if not isinstance(row['cantidad_mensual'], (int, float)) or row['cantidad_mensual'] <= 0:
                errores.append(f"Fila {fila}: cantidad_mensual debe ser positiva")
            if not isinstance(row['elasticidad'], (int, float)) or row['elasticidad'] >= 0:
                errores.append(f"Fila {fila}: elasticidad debe ser negativa (ej: -1.4)")
            if not isinstance(row['costo_variable_pct'], (int, float)) or not (0 < row['costo_variable_pct'] < 1):
                errores.append(f"Fila {fila}: costo_variable_pct debe estar entre 0 y 1 (ej: 0.45)")
            if not isinstance(row['r2'], (int, float)) or not (0 < row['r2'] <= 1):
                errores.append(f"Fila {fila}: r2 debe estar entre 0 y 1")

        if errores:
            return {
                "error": "Errores de validación en los datos",
                "detalle": errores,
                "ayuda": "Corrige los errores y vuelve a subir el archivo."
            }

        # Cargar datos
        nuevos_productos = {}
        for _, row in df.iterrows():
            nombre = str(row['producto']).strip()
            nuevos_productos[nombre] = {
                "precio_actual": round(float(row['precio_actual']), 2),
                "cantidad_mensual": int(row['cantidad_mensual']),
                "elasticidad": round(float(row['elasticidad']), 2),
                "costo_variable_pct": round(float(row['costo_variable_pct']), 2),
                "tipo": clasificar_elasticidad(float(row['elasticidad'])),
                "r2": round(float(row['r2']), 2)
            }

        PRODUCTOS = nuevos_productos
        EMPRESA_NOMBRE = archivo.filename.replace('.xlsx', '').replace('.xls', '').replace('_', ' ').title()

        return {
            "mensaje": f"Datos cargados exitosamente: {len(PRODUCTOS)} productos",
            "empresa": EMPRESA_NOMBRE,
            "productos_cargados": list(PRODUCTOS.keys()),
            "detalle": {nombre: {"precio": p["precio_actual"], "elasticidad": p["elasticidad"], "tipo": p["tipo"]} for nombre, p in PRODUCTOS.items()},
            "siguiente_paso": "Ahora ve a Copilot Studio y pregúntale al agente sobre tus productos. Ejemplo: '¿Cuál es el precio óptimo de [tu producto]?'"
        }

    except Exception as e:
        return {
            "error": f"No se pudo leer el archivo: {str(e)}",
            "ayuda": "Asegúrate de que el archivo sea un Excel válido (.xlsx) con las columnas correctas."
        }


# ===========================================================
# ENDPOINT PRINCIPAL
# ===========================================================
@app.get("/", summary="Obtener todos los datos", tags=["Consultas"])
def obtener_todos_los_datos():
    """
    Devuelve TODOS los datos de pricing en tiempo real:
    productos con elasticidades, precios actuales, cantidades,
    precio optimo calculado y tipo de elasticidad.
    """
    productos_con_optimo = []
    for nombre, p in PRODUCTOS.items():
        e = p["elasticidad"]
        cv = round(p["precio_actual"] * p["costo_variable_pct"], 2)
        ingreso_mensual = round(p["precio_actual"] * p["cantidad_mensual"], 2)
        contribucion_mensual = round((p["precio_actual"] - cv) * p["cantidad_mensual"], 2)

        if abs(e) > 1:
            margen_optimo = round(-1 / e, 4)
            precio_optimo = round(cv / (1 - margen_optimo), 2)
            diferencia_precio = round(precio_optimo - p["precio_actual"], 2)
            accion = "Subir" if diferencia_precio > 0 else "Bajar"
        else:
            margen_optimo = None
            precio_optimo = None
            diferencia_precio = None
            accion = "Subir (inelastico, soporta aumento)"

        productos_con_optimo.append({
            "producto": nombre,
            "precio_actual": p["precio_actual"],
            "cantidad_mensual": p["cantidad_mensual"],
            "elasticidad": e,
            "tipo_elasticidad": p["tipo"],
            "r2_modelo": p["r2"],
            "costo_variable_unitario": cv,
            "ingreso_mensual": ingreso_mensual,
            "contribucion_mensual": contribucion_mensual,
            "margen_optimo_pct": margen_optimo,
            "precio_optimo": precio_optimo,
            "diferencia_vs_actual": diferencia_precio,
            "accion_recomendada": accion,
        })

    resumen = {
        "empresa": EMPRESA_NOMBRE,
        "ubicacion": "Lima, Peru",
        "periodo_datos": "24 meses",
        "metodo": "Regresion log-log (ln precio vs ln cantidad)",
        "costo_variable_pct": "Porcentaje del precio (varía por producto)",
        "total_productos": len(PRODUCTOS),
        "productos_elasticos": sum(1 for p in PRODUCTOS.values() if abs(p["elasticidad"]) > 1),
        "productos_inelasticos": sum(1 for p in PRODUCTOS.values() if abs(p["elasticidad"]) <= 1),
    }

    return {
        "resumen_empresa": resumen,
        "productos": productos_con_optimo,
        "instrucciones": "Usa los endpoints /simular, /precio-optimo, /montecarlo y /comparar para analisis detallados."
    }


@app.get("/productos", summary="Listar productos", tags=["Consultas"])
def listar_productos():
    """Lista todos los productos disponibles con sus elasticidades."""
    return {
        "empresa": EMPRESA_NOMBRE,
        "total": len(PRODUCTOS),
        "productos": [
            {"nombre": k, "precio": v["precio_actual"], "elasticidad": v["elasticidad"], "tipo": v["tipo"]}
            for k, v in PRODUCTOS.items()
        ]
    }


# ===========================================================
# SIMULADOR DE ESCENARIOS
# ===========================================================
@app.post("/simular", summary="Simular cambio de precio", tags=["Análisis"])
def simular_cambio_precio(req: SimularRequest):
    """
    Simula que pasa si cambias el precio de un producto X%.
    Ejemplo: producto='Cafe Clasico', cambio_precio_pct=-15
    """
    if req.producto not in PRODUCTOS:
        return {"error": f"Producto '{req.producto}' no encontrado. Productos disponibles: {list(PRODUCTOS.keys())}"}
    return calcular_simulacion(req.producto, req.cambio_precio_pct)


# ===========================================================
# PRECIO ÓPTIMO
# ===========================================================
@app.post("/precio-optimo", summary="Calcular precio óptimo", tags=["Análisis"])
def calcular_precio_optimo(req: PrecioOptimoRequest):
    """
    Calcula el precio optimo que maximiza la contribucion total.
    Formula: Margen optimo = -1/Elasticidad, Precio optimo = CV / (1 - Margen)
    """
    if req.producto not in PRODUCTOS:
        return {"error": f"Producto '{req.producto}' no encontrado. Productos disponibles: {list(PRODUCTOS.keys())}"}

    p = PRODUCTOS[req.producto]
    e = p["elasticidad"]
    cv = round(p["precio_actual"] * p["costo_variable_pct"], 2)

    if abs(e) <= 1:
        return {
            "producto": req.producto,
            "elasticidad": e,
            "tipo": "Inelastico",
            "mensaje": "Demanda inelastica (|E| < 1). No aplica formula de margen optimo. Se puede subir el precio con confianza porque los clientes son poco sensibles.",
            "recomendacion": "Subir precio gradualmente (5-10%) y monitorear impacto."
        }

    margen_optimo = round(-1 / e, 4)
    precio_optimo = round(cv / (1 - margen_optimo), 2)
    diff = round(precio_optimo - p["precio_actual"], 2)

    return {
        "producto": req.producto,
        "elasticidad": e,
        "costo_variable_unitario": cv,
        "margen_optimo_pct": round(margen_optimo * 100, 1),
        "precio_optimo": precio_optimo,
        "precio_actual": p["precio_actual"],
        "diferencia": diff,
        "accion": f"{'Subir' if diff > 0 else 'Bajar'} S/{abs(diff):.2f}",
        "formula_usada": f"Margen = -1/{e} = {margen_optimo:.2%}. Precio = {cv} / (1 - {margen_optimo:.2f}) = S/{precio_optimo}"
    }


# ===========================================================
# SIMULACIÓN MONTE CARLO
# ===========================================================
@app.post("/montecarlo", summary="Simulación Monte Carlo", tags=["Análisis"])
def simulacion_montecarlo(req: MonteCarloRequest):
    """
    Simula N escenarios con incertidumbre en elasticidad y costos.
    Responde: cual es la PROBABILIDAD de que el cambio de precio sea rentable?
    """
    if req.producto not in PRODUCTOS:
        return {"error": f"Producto '{req.producto}' no encontrado. Productos disponibles: {list(PRODUCTOS.keys())}"}

    p = PRODUCTOS[req.producto]
    np.random.seed(42)

    elasticidades = np.random.normal(p["elasticidad"], req.desviacion_elasticidad, req.n_simulaciones)
    costos = np.random.normal(p["costo_variable_pct"], req.desviacion_costo, req.n_simulaciones)

    deltas = []
    for e_sim, c_sim in zip(elasticidades, costos):
        p_act = p["precio_actual"]
        p_new = p_act * (1 + req.cambio_precio_pct / 100)
        q_act = p["cantidad_mensual"]
        q_new = q_act * (p_new / p_act) ** e_sim
        contrib_antes = (p_act - p_act * c_sim) * q_act
        contrib_despues = (p_new - p_new * c_sim) * q_new
        deltas.append(contrib_despues - contrib_antes)

    deltas = np.array(deltas)
    prob_positivo = float((deltas > 0).mean())
    media = float(np.mean(deltas))
    percentil_5 = float(np.percentile(deltas, 5))
    percentil_95 = float(np.percentile(deltas, 95))

    return {
        "producto": req.producto,
        "escenario": f"Cambio de precio: {req.cambio_precio_pct:+.1f}%",
        "n_simulaciones": req.n_simulaciones,
        "incertidumbre_elasticidad": f"E = {p['elasticidad']} +/- {req.desviacion_elasticidad}",
        "incertidumbre_costo": f"CV = {p['costo_variable_pct']:.0%} +/- {req.desviacion_costo:.0%}",
        "probabilidad_ganar": f"{prob_positivo:.1%}",
        "probabilidad_perder": f"{1 - prob_positivo:.1%}",
        "impacto_promedio": f"S/{media:,.0f}",
        "peor_caso_5pct": f"S/{percentil_5:,.0f}",
        "mejor_caso_95pct": f"S/{percentil_95:,.0f}",
        "recomendacion": f"Con {prob_positivo:.0%} de probabilidad de ganar, {'SI se recomienda' if prob_positivo > 0.6 else 'se debe evaluar con cautela' if prob_positivo > 0.4 else 'NO se recomienda'} este cambio de precio."
    }


# ===========================================================
# COMPARADOR DE ESCENARIOS
# ===========================================================
@app.post("/comparar", summary="Comparar escenarios de precio", tags=["Análisis"])
def comparar_escenarios(req: CompararRequest):
    """
    Compara multiples cambios de precio para un producto.
    Ejemplo: escenarios=[-20, -10, 0, 10, 20]
    """
    if req.producto not in PRODUCTOS:
        return {"error": f"Producto '{req.producto}' no encontrado. Productos disponibles: {list(PRODUCTOS.keys())}"}

    resultados = []
    for cambio in req.escenarios:
        sim = calcular_simulacion(req.producto, cambio)
        resultados.append({
            "cambio_pct": cambio,
            "precio": sim["precio_nuevo"],
            "cantidad": sim["cantidad_nueva"],
            "ingreso": sim["ingreso_despues"],
            "contribucion": sim["contribucion_despues"],
            "impacto_neto": sim["impacto_neto"],
            "conviene": sim["conviene"]
        })

    mejor = max(resultados, key=lambda x: x["contribucion"])

    return {
        "producto": req.producto,
        "elasticidad": PRODUCTOS[req.producto]["elasticidad"],
        "escenarios": resultados,
        "mejor_escenario": {
            "cambio_pct": mejor["cambio_pct"],
            "contribucion": mejor["contribucion"],
            "mensaje": f"El mejor escenario es {'subir' if mejor['cambio_pct'] > 0 else 'bajar'} {abs(mejor['cambio_pct'])}% el precio, generando S/{mejor['contribucion']:,.0f} de contribucion mensual."
        }
    }
