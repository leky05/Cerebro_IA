import os
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class TelegramNotifier:
    """
    Módulo de comunicación para enviar alertas y GRÁFICOS de Cerebro_IA.
    """
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not self.token or not self.chat_id:
            print("⚠️ Faltan credenciales de Telegram en el archivo .env")

    def enviar_mensaje(self, mensaje):
        """Manda solo texto plano con formato HTML"""
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": mensaje, "parse_mode": "HTML"}
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"❌ Error enviando mensaje a Telegram: {e}")

    def enviar_foto(self, foto_path, caption):
        """Manda una imagen con un texto explicativo (caption) debajo"""
        url = f"https://api.telegram.org/bot{self.token}/sendPhoto"
        try:
            # Abrimos el archivo de imagen en modo binario
            with open(foto_path, 'rb') as foto:
                files = {'photo': foto}
                data = {
                    'chat_id': self.chat_id,
                    'caption': caption,
                    'parse_mode': 'HTML'
                }
                respuesta = requests.post(url, files=files, data=data)
                
                if respuesta.status_code == 200:
                    print("✅ Gráfico enviado a Telegram con éxito.")
                else:
                    print(f"❌ Error al enviar foto: {respuesta.text}")
        except FileNotFoundError:
            print(f"❌ No se encontró el archivo de gráfico en: {foto_path}")
            self.enviar_mensaje(caption) # Si falla la foto, manda el texto igual
        except Exception as e:
            print(f"❌ Error de conexión al enviar foto a Telegram: {e}")

if __name__ == "__main__":
    print("Módulo TelegramNotifier (v2.0 con soporte de fotos) listo.")