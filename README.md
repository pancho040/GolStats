# GolStats Bot · Alertas de Fútbol para Telegram

Bot personal para Telegram que monitorea partidos de fútbol, envía recordatorios (24h y 1h antes) y resúmenes post-partido con estadísticas, goles y enlaces a repeticiones.

Configurado con la hora local de **Sucre, Bolivia (UTC-4)** y con diseño **minimalista**.

---

## 📱 Comandos en Telegram

Puedes enviar estos comandos directamente al bot en cualquier momento:

- `/proximos` — Lista los partidos programados de tus equipos en los próximos 7 días con fecha y hora local.
- `/equipos` — Muestra la lista actual de equipos y ligas configuradas.
- `/agregar <nombre>` — Agrega un nuevo equipo a tu lista de alertas (ej: `/agregar Inter Miami`).
- `/quitar <nombre>` — Elimina un equipo de tus alertas (ej: `/quitar Chelsea`).
- `/resultados` — Consulta los marcadores y estadísticas de partidos recientes.
- `/ayuda` — Muestra el menú de ayuda.

---

## ⚡ Equipos y Ligas Preconfigurados

1. **Premier League**: Manchester City, Arsenal, Liverpool, Manchester United, Chelsea, Tottenham Hotspur.
2. **La Liga de España**: Real Madrid, Barcelona, Atlético de Madrid.
3. **División Profesional de Bolivia**: Monitoreo de todos los partidos (Independiente Petrolero, Bolívar, The Strongest, etc.).
4. **UEFA Champions League**: A partir de fases eliminatorias.

---

## ☁️ Cómo tenerlo funcionando 24/7 Gratis (Sin encender tu PC)

Para que el bot funcione siempre sin necesidad de dejar tu computadora prendida, puedes subirlo a **Hugging Face Spaces** (100% gratis, sin tarjeta de crédito y nunca se apaga):

1. Entra a [huggingface.co](https://huggingface.co) y crea una cuenta gratuita.
2. Haz clic en tu perfil arriba a la derecha y selecciona **New Space**.
3. Elige:
   - **Space name**: `golstats-bot`
   - **License**: `mit`
   - **Space SDK**: **Docker** -> **Blank**
   - **Space hardware**: `CPU basic · 2 vCPU · 16 GB` (Gratis)
4. Haz clic en **Create Space**.
5. Ve a la pestaña **Files** -> **Add file** -> **Upload files**, y arrastra todos los archivos de esta carpeta:
   - `bot.py`
   - `espn_service.py`
   - `telegram_service.py`
   - `scheduler.py`
   - `config.json`
   - `state.json`
   - `requirements.txt`
   - `Dockerfile`
6. Haz clic en **Commit changes to main**.

¡Listo! Hugging Face compilará el contenedor y tu bot estará activo 24/7 en la nube enviándote alertas a Telegram.
