"""
build.py — Genera el objeto DATA para el dashboard de elasticidades.

Lee los 3 Excels (AR, CL, UY) desde Google Drive (via Service Account),
calcula TOTAL = suma de los 3, computa elasticidades y costos marginales
con ventana base (4 semanas) vs actual (últimas 2 semanas), y produce
un data.json con la misma forma que el objeto DATA hardcodeado del HTML.

Uso local (para testear sin Drive):
    python build.py --local

Uso en producción (via GitHub Actions):
    python build.py
"""

import argparse
import io
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent.resolve()
load_dotenv(SCRIPT_DIR / ".env")

# --- Config ----------------------------------------------------------------

WEEK_COL = "Semana\xa0N"  # el nbsp está en el nombre de columna original
ACTUAL_WINDOW = 2   # últimas N semanas = "actual"
BASE_WINDOW = 4     # N semanas previas al actual = "base"

# Si el spend de la última semana es < este % de la mediana de las 4 previas,
# asumimos que la semana está incompleta (todavía cargándose) y emitimos warning.
INCOMPLETE_SPEND_RATIO = 0.6

# Mapping UY → schema canónico (el de AR/CL)
UY_RENAME = {
    "Total_Purchase": "Purchase_Totales",
    "Purchase_Search": "purchase_search",
    "Purchase_PMAX": "purchase_pmax",
    "Purchase_Meta": "purchase_meta",
    "Total Spend": "Spend Total",
    "session_start_organic": "Sesiones Organico",
    "session_start_search": "Sesiones Search",
    "session_start_meta": "Sesiones Meta",
    "session_start_pmax": "Sesiones PMAX",
    "session_start_others": "Sesiones Others",
}

COUNTRIES = {
    "AR": {"env_var": "FILE_ID_AR", "local_path": "Base_Claude_Elasticidad_AR.xlsx", "sheet": "BASE AR"},
    "CL": {"env_var": "FILE_ID_CL", "local_path": "Base_Claude_Elasticidad_CL.xlsx", "sheet": "BASE CL"},
    "UY": {"env_var": "FILE_ID_UY", "local_path": "Base_Claude_Elasticidad_UY.xlsx", "sheet": "Base_UY"},
}


# --- Descarga desde Drive --------------------------------------------------

def get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    creds_path = SCRIPT_DIR / "credentials.json"
    if not creds_path.exists():
        raise FileNotFoundError(f"No encuentro {creds_path}")
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def download_from_drive(service, file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

    XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    GSHEET_MIME = "application/vnd.google-apps.spreadsheet"

    meta = service.files().get(fileId=file_id, fields="name, mimeType").execute()
    if meta.get("mimeType") == GSHEET_MIME:
        request = service.files().export_media(fileId=file_id, mimeType=XLSX_MIME)
    else:
        request = service.files().get_media(fileId=file_id)

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def load_country_df(country: str, local: bool) -> pd.DataFrame:
    """Devuelve el DataFrame del país, filtrado al año más reciente y ordenado por semana."""
    cfg = COUNTRIES[country]
    if local:
        path = SCRIPT_DIR.parent / cfg["local_path"]
        if not path.exists():
            # fallback a carpeta padre (cuando se corre desde repo/)
            path = SCRIPT_DIR.parent.parent / cfg["local_path"]
        print(f"  [{country}] leyendo local: {path}")
        df = pd.read_excel(path, sheet_name=cfg["sheet"])
    else:
        file_id = (os.getenv(cfg["env_var"]) or "").strip()
        if not file_id:
            raise ValueError(f"Falta el env var {cfg['env_var']}")
        print(f"  [{country}] bajando de Drive (id len={len(file_id)})...")
        service = get_drive_service()
        content = download_from_drive(service, file_id)
        df = pd.read_excel(io.BytesIO(content), sheet_name=cfg["sheet"])

    # Normalizar UY al schema canónico
    if country == "UY":
        df = df.rename(columns=UY_RENAME)
        # UY no trae sesiones_totales → lo derivamos
        df["sesiones_totales"] = (
            df["Sesiones Organico"] + df["Sesiones Search"] +
            df["Sesiones Meta"] + df["Sesiones PMAX"] + df["Sesiones Others"]
        )

    # Filtrar al año más reciente
    latest_year = int(df["Año"].max())
    df = df[df["Año"] == latest_year].copy()

    # Normalizar nombre de semana: strip + uppercase (algunos Excels tienen "W1 " con espacio)
    df[WEEK_COL] = df[WEEK_COL].astype(str).str.strip().str.upper()

    # Ordenar por número de semana (W1, W2, ..., W52)
    df["_week_num"] = df[WEEK_COL].str.extract(r"(\d+)").astype(int)
    df = df.sort_values("_week_num").reset_index(drop=True)
    return df


# --- Extracción de series (bloque "evo") -----------------------------------

def extract_evo(df: pd.DataFrame) -> Dict:
    """Devuelve el bloque evo: weeks + arrays por columna."""
    weeks = df[WEEK_COL].tolist()

    # google = search + pmax
    purch_google = (df["purchase_search"] + df["purchase_pmax"]).tolist()
    ses_google = (df["Sesiones Search"] + df["Sesiones PMAX"]).tolist()

    return {
        "weeks": weeks,
        "spend_google": df["Spend Google"].tolist(),
        "spend_meta": df["Spend Meta"].tolist(),
        "spend_total": df["Spend Total"].tolist(),
        "purch_total": df["Purchase_Totales"].tolist(),
        "purch_search": df["purchase_search"].tolist(),
        "purch_pmax": df["purchase_pmax"].tolist(),
        "purch_meta": df["purchase_meta"].tolist(),
        "purch_organic": df["Purchase_Organic"].tolist(),
        "purch_others": df["Purchase_Others"].tolist(),
        "ses_total": df["sesiones_totales"].tolist(),
        "ses_search": df["Sesiones Search"].tolist(),
        "ses_pmax": df["Sesiones PMAX"].tolist(),
        "ses_meta": df["Sesiones Meta"].tolist(),
        "ses_organic": df["Sesiones Organico"].tolist(),
        "ses_others": df["Sesiones Others"].tolist(),
    }


# --- Cálculo del bloque "elas" ---------------------------------------------

def avg(lst: List[float]) -> float:
    return sum(lst) / len(lst)


def channel_block(
    purch_series: List[float],
    ses_series: List[float],
    spend_series: List[float] | None,
    base_idx: List[int],
    actual_idx: List[int],
) -> Dict:
    """Bloque para un canal. Si spend_series es None, no incluye spend ni métricas derivadas."""
    purch_base = avg([purch_series[i] for i in base_idx])
    purch_actual = avg([purch_series[i] for i in actual_idx])
    purch_nom = purch_actual - purch_base
    purch_pct = (purch_nom / purch_base * 100) if purch_base else 0.0

    out = {
        "purch_base": round(purch_base, 1),
        "purch_actual": round(purch_actual, 1),
        "purch_nom": round(purch_nom, 1),
        "purch_pct": round(purch_pct, 2),
    }

    if spend_series is None:
        return out  # organic / others: solo purchases

    spend_base = avg([spend_series[i] for i in base_idx])
    spend_actual = avg([spend_series[i] for i in actual_idx])
    spend_nom = spend_actual - spend_base
    spend_pct = (spend_nom / spend_base * 100) if spend_base else 0.0

    ses_base = avg([ses_series[i] for i in base_idx])
    ses_actual = avg([ses_series[i] for i in actual_idx])
    ses_nom = ses_actual - ses_base
    ses_pct = (ses_nom / ses_base * 100) if ses_base else 0.0

    e_purch = (purch_pct / spend_pct) if spend_pct else 0.0
    e_ses = (ses_pct / spend_pct) if spend_pct else 0.0
    mc_purch = (spend_nom / purch_nom) if purch_nom else 0.0
    mc_ses = (spend_nom / ses_nom) if ses_nom else 0.0

    out.update({
        "spend_base": round(spend_base, 2),
        "spend_actual": round(spend_actual, 2),
        "spend_nom": round(spend_nom, 2),
        "spend_pct": round(spend_pct, 2),
        "ses_base": round(ses_base, 1),
        "ses_actual": round(ses_actual, 1),
        "ses_nom": round(ses_nom, 1),
        "ses_pct": round(ses_pct, 2),
        "e_purch": round(e_purch, 3),
        "e_ses": round(e_ses, 3),
        "mc_purch": round(mc_purch, 4),
        "mc_ses": round(mc_ses, 6),
    })
    # Reordenar para que spend venga antes de purch (como en el HTML)
    ordered_keys = [
        "spend_base", "spend_actual", "spend_nom", "spend_pct",
        "purch_base", "purch_actual", "purch_nom", "purch_pct",
        "ses_base", "ses_actual", "ses_nom", "ses_pct",
        "e_purch", "e_ses", "mc_purch", "mc_ses",
    ]
    return {k: out[k] for k in ordered_keys}


def extract_elas(evo: Dict) -> Dict:
    """Calcula bloque elas (base vs actual, elasticidad, mc) para todos los canales."""
    weeks = evo["weeks"]
    n = len(weeks)
    if n < ACTUAL_WINDOW + BASE_WINDOW:
        raise ValueError(
            f"Necesito al menos {ACTUAL_WINDOW + BASE_WINDOW} semanas; "
            f"hay {n}."
        )

    actual_idx = list(range(n - ACTUAL_WINDOW, n))
    base_idx = list(range(n - ACTUAL_WINDOW - BASE_WINDOW, n - ACTUAL_WINDOW))

    base_weeks_label = f"{weeks[base_idx[0]]}–{weeks[base_idx[-1]]}"
    actual_weeks_label = f"{weeks[actual_idx[0]]}–{weeks[actual_idx[-1]]}"

    return {
        "total": channel_block(
            evo["purch_total"], evo["ses_total"], evo["spend_total"],
            base_idx, actual_idx,
        ),
        "google": channel_block(
            [a + b for a, b in zip(evo["purch_search"], evo["purch_pmax"])],
            [a + b for a, b in zip(evo["ses_search"], evo["ses_pmax"])],
            evo["spend_google"],
            base_idx, actual_idx,
        ),
        "meta": channel_block(
            evo["purch_meta"], evo["ses_meta"], evo["spend_meta"],
            base_idx, actual_idx,
        ),
        "organic": channel_block(
            evo["purch_organic"], evo["ses_organic"], None,
            base_idx, actual_idx,
        ),
        "others": channel_block(
            evo["purch_others"], evo["ses_others"], None,
            base_idx, actual_idx,
        ),
        "base_weeks": base_weeks_label,
        "actual_weeks": actual_weeks_label,
    }


# --- Detección de warnings -------------------------------------------------

def detect_warnings(result: Dict) -> List[Dict]:
    """
    Emite warnings si:
      (a) los 3 países no terminan en la misma semana (→ el TOTAL mezcla
          semanas distintas y puede dar lecturas misleading).
      (b) alguna última semana de país tiene spend muy por debajo de la mediana
          de las 4 previas (→ probablemente la semana no cerró todavía).
    """
    import statistics

    warnings: List[Dict] = []

    # (a) semanas desalineadas entre países
    last_weeks = {c: result[c]["evo"]["weeks"][-1] for c in ("AR", "CL", "UY")}
    if len(set(last_weeks.values())) > 1:
        detail = ", ".join(f"{c}: {w}" for c, w in last_weeks.items())
        warnings.append({
            "type": "week_mismatch",
            "severity": "warning",
            "countries": last_weeks,
            "message": (
                f"Los países no terminan en la misma semana ({detail}). "
                f"El TOTAL suma semanas no comparables; "
                f"sincronizá los 3 Excels para evitar lecturas engañosas."
            ),
        })

    # (b) última semana potencialmente incompleta (por país)
    for country in ("AR", "CL", "UY"):
        spend = result[country]["evo"]["spend_total"]
        weeks = result[country]["evo"]["weeks"]
        if len(spend) < 5:
            continue
        last_spend = float(spend[-1])
        prev_4 = [float(x) for x in spend[-5:-1]]
        median_prev = statistics.median(prev_4)
        if median_prev <= 0:
            continue
        ratio = last_spend / median_prev
        if ratio < INCOMPLETE_SPEND_RATIO:
            warnings.append({
                "type": "incomplete_week",
                "severity": "warning",
                "country": country,
                "week": weeks[-1],
                "ratio": round(ratio, 2),
                "message": (
                    f"La última semana de {country} ({weeks[-1]}) parece incompleta: "
                    f"spend ${last_spend:,.0f} vs mediana de las 4 semanas previas "
                    f"${median_prev:,.0f} ({ratio*100:.0f}%). "
                    f"Si la semana todavía no cerró, los cálculos actual vs base "
                    f"pueden estar sesgados."
                ),
            })

    return warnings


# --- TOTAL = suma de países ------------------------------------------------

def build_total_df(country_dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Suma AR+CL+UY semana a semana (intersección de semanas presentes en todos)."""
    numeric_cols = [
        "Purchase_Totales", "Purchase_Organic", "purchase_meta", "purchase_search",
        "purchase_pmax", "Purchase_Others", "sesiones_totales",
        "Sesiones Organico", "Sesiones Meta", "Sesiones Search", "Sesiones PMAX",
        "Sesiones Others", "Spend Google", "Spend Meta", "Spend Total",
    ]
    merged = None
    for df in country_dfs.values():
        sub = df.set_index(WEEK_COL)[numeric_cols]
        merged = sub if merged is None else merged.add(sub, fill_value=0)
    # Restaurar orden por _week_num
    merged = merged.reset_index()
    merged["_week_num"] = merged[WEEK_COL].str.extract(r"(\d+)").astype(int)
    merged = merged.sort_values("_week_num").reset_index(drop=True)
    return merged


# --- Main ------------------------------------------------------------------

def build_data(local: bool = False) -> Dict:
    print("Cargando países...")
    dfs = {c: load_country_df(c, local=local) for c in COUNTRIES}

    print("Calculando TOTAL...")
    total_df = build_total_df(dfs)

    print("Extrayendo bloques evo + elas...")
    result = {}
    for key, df in [("TOTAL", total_df), ("AR", dfs["AR"]), ("CL", dfs["CL"]), ("UY", dfs["UY"])]:
        evo = extract_evo(df)
        elas = extract_elas(evo)
        result[key] = {"evo": evo, "elas": elas}
        print(f"  {key}: {len(evo['weeks'])} semanas, ventanas {elas['base_weeks']} / {elas['actual_weeks']}")

    print("Chequeando warnings...")
    result["warnings"] = detect_warnings(result)
    if result["warnings"]:
        print(f"  [WARN] {len(result['warnings'])} warning(s) detectado(s):")
        for w in result["warnings"]:
            print(f"    - {w['type']}: {w['message']}")
    else:
        print("  OK: sin warnings.")

    return result


DATA_MARKER = "/*__BUILD_DATA__*/{}"


def render_html(template_path: Path, data: Dict) -> str:
    """Lee el template y reemplaza el marcador por el JSON del DATA."""
    template = template_path.read_text(encoding="utf-8")
    count = template.count(DATA_MARKER)
    if count != 1:
        raise ValueError(
            f"El template {template_path.name} debería tener exactamente 1 "
            f"marcador {DATA_MARKER!r}, encontré {count}."
        )
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return template.replace(DATA_MARKER, data_json)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true", help="Leer Excels locales en vez de Drive")
    parser.add_argument("--json-out", default="data.json", help="Path del JSON (default: data.json)")
    parser.add_argument("--html-out", default="index.html", help="Path del HTML (default: index.html)")
    parser.add_argument("--template", default="template.html", help="Template HTML (default: template.html)")
    parser.add_argument("--skip-html", action="store_true", help="No generar el index.html")
    args = parser.parse_args()

    data = build_data(local=args.local)

    # 1) Escribir data.json
    json_path = SCRIPT_DIR / args.json_out
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Escrito {json_path} ({json_path.stat().st_size:,} bytes)")

    # 2) Escribir index.html (salvo --skip-html)
    if not args.skip_html:
        template_path = SCRIPT_DIR / args.template
        if not template_path.exists():
            print(f"[WARN] No encuentro {template_path}, salteando HTML.")
            return
        html = render_html(template_path, data)
        html_path = SCRIPT_DIR / args.html_out
        html_path.write_text(html, encoding="utf-8")
        print(f"[OK] Escrito {html_path} ({html_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
