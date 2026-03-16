import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class CerebroIA:
    """
    Motor de Inferencia de Cerebro_IA.
    Actualizado al nuevo estándar SDK institucional (google-genai).
    """
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("⚠️ ALERTA: No se encontró GEMINI_API_KEY en el archivo .env")
        
        # Inicializamos el cliente con el nuevo SDK
        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-2.5-flash' # Motor actualizado
        
        # Cargar el Prompt Maestro
        prompt_path = os.path.join(os.path.dirname(__file__), 'prompt_maestro.txt')
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.prompt_maestro = f.read()

    def analizar_setup(self, fvg_data, velas_json):
        print(f"🧠 Cerebro_IA ({self.model_id}) analizando la microestructura...")
        
        # Ensamblar el mensaje con las instrucciones y los datos crudos
        mensaje = f"""
        {self.prompt_maestro}
        
        --- DATOS DEL MERCADO ACTUAL ---
        
        DATOS DEL FVG ACTIVO:
        {json.dumps(fvg_data, indent=2)}
        
        ACCIÓN DEL PRECIO (Últimas velas en la zona):
        {json.dumps(velas_json, indent=2)}
        """
        
        try:
            # Llamar a la Red Neuronal con la nueva configuración JSON
            respuesta = self.client.models.generate_content(
                model=self.model_id,
                contents=mensaje,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            return json.loads(respuesta.text)
        except Exception as e:
            print(f"❌ Error en la sinapsis: {e}")
            return {"signal": 0, "reasoning": "Error de conexión o parseo JSON."}

if __name__ == "__main__":
    # --- PRUEBA DE FUEGO: EL SET-UP PERFECTO ---
    print("🚀 Iniciando Prueba de Fuego del Cerebro Artificial...")
    
    try:
        cerebro = CerebroIA()
        
        # 1. El Radar Quant informa de un FVG Alcista (Zona de Compras)
        fvg_simulado = {
            "tipo": "Alcista (Long)",
            "techo_fvg": 2010.50,
            "base_fvg": 2008.00
        }
        
        # 2. El Radar empaqueta las últimas 4 velas
        velas_simuladas = [
            {"vela": -3, "open": 2015.0, "high": 2016.0, "low": 2011.0, "close": 2011.5, "vol_relativo": 0.8, "nota": "Cae hacia la zona"},
            {"vela": -2, "open": 2011.5, "high": 2012.0, "low": 2009.5, "close": 2010.0, "vol_relativo": 0.9, "nota": "Crea PL interno en el Low de 2009.5"},
            {"vela": -1, "open": 2010.0, "high": 2010.0, "low": 2007.5, "close": 2009.0, "vol_relativo": 2.1, "nota": "¡Sweep! Baja a 2007.5 (rompe PL), entra al FVG, respeta base 2008 con el cuerpo. Martillo."},
            {"vela": 0,  "open": 2009.0, "high": 2014.0, "low": 2009.0, "close": 2013.8, "vol_relativo": 1.8, "nota": "Vela envolvente alcista (Gatillo B)."}
        ]
        
        # 3. La IA toma el control
        decision = cerebro.analizar_setup(fvg_simulado, velas_simuladas)
        
        print("\n🎯 DECISIÓN DE LA IA:")
        print(json.dumps(decision, indent=4, ensure_ascii=False))
        
    except Exception as error_fatal:
        print(f"Error crítico: {error_fatal}")