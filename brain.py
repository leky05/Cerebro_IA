import os
import re
import json
import time
from google import genai
from google.genai import types
from google.api_core.exceptions import (
    ResourceExhausted,
    DeadlineExceeded,
    ServiceUnavailable,
    GoogleAPICallError,
)
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


class CerebroIA:
    """
    Motor de Inferencia de Cerebro_IA v2.2 — Blindaje API
    ======================================================
    Changelog vs v2.1:
      - Throttle anti-RPM configurable entre cada llamada exitosa.
      - Excepciones tipadas de google.api_core para detección precisa.
      - Logging estructurado con prefijos de severidad.
      - Fallback seguro: CUALQUIER excepción no prevista retorna
        señal neutral (0) sin crashear el loop.

    Resiliente contra:
      - Cuota diaria Free Tier agotada → aborta y señaliza al backtester.
      - Rate Limit por minuto (429) → parsea retryDelay y espera.
      - Timeouts de conexión / lectura → pausa y reintenta.
      - Respuesta JSON malformada → rechaza el trade limpiamente.
      - Errores desconocidos → señal neutral, log y continúa.
    """

    # ── Parámetros de Resiliencia ─────────────────────────────────
    MAX_REINTENTOS = 3
    TIMEOUT_SEGUNDOS = 120            # Máximo de espera por respuesta
    PAUSA_RATE_LIMIT_DEFAULT = 35     # Fallback si no puede parsear retryDelay
    PAUSA_ERROR_RED = 15              # Pausa ante timeout/conexión
    PAUSA_ENTRE_CONSULTAS = 3         # Throttle anti-RPM (segundos)

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "⚠️ ALERTA: No se encontró GEMINI_API_KEY en el archivo .env"
            )

        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=self.TIMEOUT_SEGUNDOS * 1000
            ),
        )
        self.model_id = "gemini-2.5-flash"

        prompt_path = os.path.join(
            os.path.dirname(__file__), "prompt_maestro.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.prompt_maestro = f.read()

    # ──────────────────────────────────────────────────────────────
    # MÉTODO PRINCIPAL — Análisis de setup con blindaje completo
    # ──────────────────────────────────────────────────────────────
    def analizar_setup(self, fvg_data, velas_json):
        """
        Envía el setup al LLM y retorna la decisión.

        Retorno especial:
          Si la cuota DIARIA se agotó, retorna:
            {"signal": 0, "reasoning": "...", "_cuota_agotada": True}
          El backtester debe revisar esta flag para frenar el loop.
        """
        print(
            f"🧠 Cerebro_IA ({self.model_id}) analizando la microestructura..."
        )

        mensaje = f"""
        {self.prompt_maestro}

        --- DATOS DEL MERCADO ACTUAL ---
        DATOS DEL FVG ACTIVO:
        {json.dumps(fvg_data, indent=2)}

        ACCIÓN DEL PRECIO (Últimas velas en la zona):
        {json.dumps(velas_json, indent=2)}
        """

        for intento in range(1, self.MAX_REINTENTOS + 1):
            try:
                respuesta = self.client.models.generate_content(
                    model=self.model_id,
                    contents=mensaje,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )

                texto_limpio = (
                    respuesta.text
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )

                resultado = json.loads(texto_limpio)

                # ── Throttle anti-RPM: pausa DESPUÉS de éxito ────────
                time.sleep(self.PAUSA_ENTRE_CONSULTAS)

                return resultado

            # ─── 1. JSON malformado ──────────────────────────────────
            except json.JSONDecodeError as e:
                print(
                    f"   ❌ [JSON Inválido] La IA devolvió texto no "
                    f"parseable: {e}"
                )
                time.sleep(self.PAUSA_ENTRE_CONSULTAS)
                return {
                    "signal": 0,
                    "reasoning": "Respuesta de IA con formato JSON inválido.",
                }

            # ─── 2. Cuota agotada / Rate Limit (429) ────────────────
            except ResourceExhausted as e:
                resultado_429 = self._manejar_rate_limit(str(e), intento)
                if resultado_429 is not None:
                    return resultado_429
                # Si retorna None, el for continúa al siguiente intento

            # ─── 3. Timeout de la API ────────────────────────────────
            except DeadlineExceeded:
                print(
                    f"   ⏱️ [Timeout API] La respuesta excedió "
                    f"{self.TIMEOUT_SEGUNDOS}s. Reintentando en "
                    f"{self.PAUSA_ERROR_RED}s... "
                    f"(Intento {intento}/{self.MAX_REINTENTOS})"
                )
                time.sleep(self.PAUSA_ERROR_RED)

            # ─── 4. Servicio no disponible (503, mantenimiento) ──────
            except ServiceUnavailable:
                print(
                    f"   🌐 [Servicio No Disponible] Gemini está "
                    f"temporalmente caído. Reintentando en "
                    f"{self.PAUSA_ERROR_RED}s... "
                    f"(Intento {intento}/{self.MAX_REINTENTOS})"
                )
                time.sleep(self.PAUSA_ERROR_RED)

            # ─── 5. Otros errores de la API de Google ────────────────
            except GoogleAPICallError as e:
                error_str = str(e)
                error_lower = error_str.lower()

                # Detectar timeout/red por mensaje (fallback del tipado)
                if any(
                    k in error_lower
                    for k in [
                        "timeout", "timed out", "read timed out",
                        "connect", "connection", "ssl", "recv",
                        "remotedisconnected", "reset by peer",
                    ]
                ):
                    print(
                        f"   🌐 [Timeout/Red] Conexión interrumpida. "
                        f"Reintentando en {self.PAUSA_ERROR_RED}s... "
                        f"(Intento {intento}/{self.MAX_REINTENTOS})"
                    )
                    time.sleep(self.PAUSA_ERROR_RED)
                else:
                    print(
                        f"   ❌ [Error API Google] {error_str[:200]}"
                    )
                    time.sleep(self.PAUSA_ENTRE_CONSULTAS)
                    return {
                        "signal": 0,
                        "reasoning": (
                            f"Error técnico API: {error_str[:100]}"
                        ),
                    }

            # ─── 6. CATCH-ALL: Cualquier error imprevisto ────────────
            except Exception as e:
                error_str = str(e)
                error_lower = error_str.lower()

                # Último intento de detectar 429 por string (por si
                # la librería lanza un tipo no estándar)
                if "429" in error_str or "resource_exhausted" in error_lower:
                    resultado_429 = self._manejar_rate_limit(
                        error_str, intento
                    )
                    if resultado_429 is not None:
                        return resultado_429
                    continue

                # Error totalmente desconocido → señal neutral y seguir
                print(
                    f"   ⚠️ [Error Desconocido] {type(e).__name__}: "
                    f"{error_str[:200]}"
                )
                time.sleep(self.PAUSA_ENTRE_CONSULTAS)
                return {
                    "signal": 0,
                    "reasoning": (
                        f"Error técnico inesperado: {error_str[:100]}"
                    ),
                }

        # ── Agotados todos los reintentos ────────────────────────────
        print(
            f"🛑 Trade abortado: {self.MAX_REINTENTOS} intentos fallidos."
        )
        time.sleep(self.PAUSA_ENTRE_CONSULTAS)
        return {
            "signal": 0,
            "reasoning": "Abortado: reintentos de API agotados.",
        }

    # ──────────────────────────────────────────────────────────────
    # HELPERS PRIVADOS
    # ──────────────────────────────────────────────────────────────
    def _manejar_rate_limit(self, error_str, intento):
        """
        Procesa un error 429 (ResourceExhausted).

        Retorna:
          - dict con _cuota_agotada=True si es cuota diaria (para frenar
            el backtester).
          - None si es rate limit por minuto (para que el for reintente).
        """
        error_lower = error_str.lower()

        es_cuota_diaria = (
            "free_tier" in error_lower
            or "perdayperproject" in error_lower
            or "perday" in error_lower
        )

        if es_cuota_diaria:
            print(
                "\n   🚫 [CUOTA DIARIA AGOTADA] El Free Tier de Gemini "
                "permite ~25 requests/día por modelo.\n"
                "   → El backtest se detendrá automáticamente.\n"
                "   → Opciones: esperar 24h, o migrar a una API key "
                "de pago."
            )
            return {
                "signal": 0,
                "reasoning": "Cuota diaria de Gemini Free Tier agotada.",
                "_cuota_agotada": True,
            }

        # Rate limit por minuto → parsear retryDelay si viene
        pausa = self._parsear_retry_delay(error_str)
        print(
            f"   ⏳ [Rate Limit/min] Pausando {pausa}s... "
            f"(Intento {intento}/{self.MAX_REINTENTOS})"
        )
        time.sleep(pausa)
        return None  # Señal para que el for continúe reintentando

    @staticmethod
    def _parsear_retry_delay(error_str):
        """
        Extrae el retryDelay del mensaje de error de Gemini.
        Ejemplo: 'retry in 29.54s' → 31 (redondeado + 2s de margen).
        """
        match = re.search(
            r"retry\s*in\s*([\d.]+)s", error_str, re.IGNORECASE
        )
        if match:
            return int(float(match.group(1))) + 2  # +2s de margen
        return CerebroIA.PAUSA_RATE_LIMIT_DEFAULT


if __name__ == "__main__":
    print("Módulo Cerebro_IA v2.2 (Blindaje API) cargado y listo.")
