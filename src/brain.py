import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class CerebroIA:
    """
    Motor de Inferencia de Cerebro_IA.
    Equipado con Anti-Rate-Limit (Espera automática para Free Tier).
    """
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("⚠️ ALERTA: No se encontró GEMINI_API_KEY en el archivo .env")
        
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-2.5-flash' 
        
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompt_maestro.txt')
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.prompt_maestro = f.read()

    def analizar_setup(self, fvg_data, velas_json, max_reintentos=3):
        print(f"🧠 Cerebro_IA ({self.model_id}) analizando la microestructura...")
        
        mensaje = f"""
        {self.prompt_maestro}
        
        --- DATOS DEL MERCADO ACTUAL ---
        DATOS DEL FVG ACTIVO:
        {json.dumps(fvg_data, indent=2)}
        
        ACCIÓN DEL PRECIO (Últimas velas en la zona):
        {json.dumps(velas_json, indent=2)}
        """
        
        # Bucle de reintentos para evadir el Error 429
        for intento in range(max_reintentos):
            try:
                respuesta = self.client.models.generate_content(
                    model=self.model_id,
                    contents=mensaje,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    )
                )
                
                texto_limpio = respuesta.text.replace("```json", "").replace("```", "").strip()
                return json.loads(texto_limpio)
                
            except Exception as e:
                error_str = str(e)
                # Si el error es por límite de cuota (429)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    print(f"   ⏳ [API Límite] Cuota excedida. Pausando el backtest 60 segundos... (Intento {intento + 1}/{max_reintentos})")
                    time.sleep(60) # Espera 1 minuto y vuelve a intentar el mismo trade
                else:
                    # Si es un error de formato JSON u otra cosa, cancelamos el trade
                    print(f"❌ Error de parseo o conexión: {error_str}")
                    return {"signal": 0, "reasoning": "Error técnico de API o Formato."}
                    
        # Si falló los 3 intentos esperando
        print("🛑 Trade abortado: Se superó el tiempo máximo de espera de la API.")
        return {"signal": 0, "reasoning": "Abortado por límite de API persistente."}

if __name__ == "__main__":
    print("Módulo Cerebro_IA cargado y listo.")