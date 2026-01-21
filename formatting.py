"""
Módulo de formateo para números, moneda COP y porcentajes.
"""


def format_cop(value):
    """
    Formatea un valor como moneda COP con separador de miles y sin decimales.
    
    Args:
        value: Número (int o float)
    
    Returns:
        str: Valor formateado (ej: "3.800.000")
    """
    if value is None:
        return ""
    try:
        num = float(value)
        if num < 0:
            return f"-{format_cop(abs(num))}"
        return f"{int(round(num)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return ""


def format_number(value, decimals=0):
    """
    Formatea un número genérico con separador de miles y decimales configurables.
    
    Args:
        value: Número (int o float)
        decimals: Número de decimales (default: 0)
    
    Returns:
        str: Valor formateado (ej: "1.234,56" si decimals=2)
    """
    if value is None:
        return ""
    try:
        num = float(value)
        if num < 0:
            return f"-{format_number(abs(num), decimals)}"
        if decimals == 0:
            return f"{int(round(num)):,}".replace(",", ".")
        else:
            formatted = f"{num:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return formatted
    except (ValueError, TypeError):
        return ""


def format_percentage(value, decimals=1):
    """
    Formatea un valor como porcentaje con decimales configurables.
    
    Args:
        value: Número (ej: 19.0 para 19%)
        decimals: Número de decimales (default: 1)
    
    Returns:
        str: Porcentaje formateado (ej: "19,0%")
    """
    if value is None:
        return ""
    try:
        num = float(value)
        if decimals == 0:
            return f"{int(round(num))}%"
        else:
            formatted = f"{num:.{decimals}f}".replace(".", ",")
            return f"{formatted}%"
    except (ValueError, TypeError):
        return ""


def parse_number(text):
    """
    Convierte un string formateado (con separadores de miles) a float.
    
    Args:
        text: String con número formateado (ej: "3.800.000" o "1.234,56")
    
    Returns:
        float: Número parseado, o 0.0 si no se puede parsear
    """
    if text is None or text == "":
        return 0.0
    try:
        # Remover espacios
        text = str(text).strip()
        # Si está vacío después de limpiar, retornar 0
        if not text:
            return 0.0
        # Reemplazar separadores: punto de miles y coma decimal
        # Primero identificar si usa coma o punto como decimal
        if "," in text and "." in text:
            # Tiene ambos: el último es el decimal
            if text.rindex(",") > text.rindex("."):
                # Coma es decimal, punto es miles
                text = text.replace(".", "").replace(",", ".")
            else:
                # Punto es decimal, coma es miles
                text = text.replace(",", "")
        elif "," in text:
            # Solo coma: podría ser decimal o miles
            # Si hay más de 3 dígitos después de la coma, probablemente es miles
            parts = text.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Probablemente decimal
                text = text.replace(",", ".")
            else:
                # Probablemente miles
                text = text.replace(",", "")
        elif "." in text:
            # Solo punto: verificar si es decimal o miles
            parts = text.split(".")
            if len(parts) == 2 and len(parts[1]) <= 2:
                # Probablemente decimal, ya está bien
                pass
            else:
                # Probablemente miles, remover puntos
                text = text.replace(".", "")
        
        return float(text)
    except (ValueError, AttributeError):
        return 0.0
