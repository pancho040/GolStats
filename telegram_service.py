import html
import requests

def escape(text):
    if not text:
        return ""
    return html.escape(str(text))

class TelegramService:
    def __init__(self, token, default_chat_id):
        self.token = token
        self.default_chat_id = default_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text, chat_id=None, reply_markup=None):
        target_id = chat_id or self.default_chat_id
        payload = {
            "chat_id": target_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        try:
            r = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=10)
            return r.status_code == 200
        except Exception as e:
            print(f"Error enviando mensaje a Telegram: {e}")
            return False

    def format_24h_alert(self, match):
        league = escape(match.get("league_name", "").upper())
        home = escape(match["home_team"].get("name", "Local"))
        away = escape(match["away_team"].get("name", "Visitante"))
        dt_local = match.get("date_local")
        date_str = dt_local.strftime("%d/%m - %H:%M") if dt_local else "Por confirmar"
        venue = escape(match.get("venue") or "Estadio por confirmar")

        return (
            f"<b>PRÓXIMO PARTIDO · {league}</b>\n\n"
            f"<b>{home} vs {away}</b>\n"
            f"🗓 Mañana, {date_str} (Hora Bolivia)\n"
            f"📍 {venue}"
        )

    def format_1h_alert(self, match):
        league = escape(match.get("league_name", "").upper())
        home = escape(match["home_team"].get("name", "Local"))
        away = escape(match["away_team"].get("name", "Visitante"))
        dt_local = match.get("date_local")
        time_str = dt_local.strftime("%H:%M") if dt_local else "En breve"
        venue = escape(match.get("venue") or "Estadio por confirmar")

        return (
            f"<b>COMIENZA EN 1 HORA · {league}</b>\n\n"
            f"<b>{home} vs {away}</b>\n"
            f"⏰ Hoy a las {time_str} (Hora Bolivia)\n"
            f"📍 {venue}"
        )

    def format_postmatch_recap(self, match):
        league = escape(match.get("league_name", "").upper())
        home_name = escape(match["home_team"].get("name", "Local"))
        away_name = escape(match["away_team"].get("name", "Visitante"))
        home_score = match["home_team"].get("score", "0")
        away_score = match["away_team"].get("score", "0")
        
        msg = f"<b>FINAL · {league}</b>\n\n"
        msg += f"<b>{home_name} {home_score} — {away_score} {away_name}</b>\n\n"
        
        # Goles
        goals = match.get("goals", [])
        if goals:
            msg += "<b>Goles:</b>\n"
            for g in goals:
                scorer = escape(g.get("player"))
                minute = escape(g.get("minute"))
                msg += f"• {scorer} ({minute})\n"
            msg += "\n"
            
        # Estadísticas clave
        stats = match.get("stats", {})
        pos_h = stats.get("home_possession", "-")
        pos_a = stats.get("away_possession", "-")
        shots_h = stats.get("home_shots", "-")
        shots_a = stats.get("away_shots", "-")
        sog_h = stats.get("home_sog", "-")
        sog_a = stats.get("away_sog", "-")
        
        if pos_h != "-" or shots_h != "-":
            msg += "<b>Estadísticas:</b>\n"
            if pos_h != "-" and pos_a != "-":
                msg += f"• Posesión: {pos_h}% — {pos_a}%\n"
            if shots_h != "-" and shots_a != "-":
                msg += f"• Tiros (al arco): {shots_h} ({sog_h}) — {shots_a} ({sog_a})\n"
            msg += "\n"
            
        # Enlace de video o resumen
        video = match.get("video_link")
        if video:
            msg += f"🎥 <a href=\"{video}\">Ver resumen en video / jugadas</a>"
            
        return msg.strip()

    def format_upcoming_list(self, matches):
        if not matches:
            return "No hay partidos programados de tus equipos en los próximos días."
            
        msg = "<b>PRÓXIMOS PARTIDOS CONFIGURADOS</b>\n\n"
        current_day = None
        
        for m in matches:
            dt = m.get("date_local")
            if not dt:
                continue
            day_str = dt.strftime("%A %d de %B").capitalize()
            if day_str != current_day:
                current_day = day_str
                msg += f"📅 <b>{current_day}</b>\n"
                
            time_str = dt.strftime("%H:%M")
            home = escape(m["home_team"].get("name", "Local"))
            away = escape(m["away_team"].get("name", "Visitante"))
            league = escape(m.get("league_name", ""))
            
            msg += f"• {time_str} | <b>{home} vs {away}</b> ({league})\n"
            
        return msg.strip()
