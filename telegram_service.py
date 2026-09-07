import html
import requests
from datetime import datetime

DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MONTHS_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

def format_date_es(dt):
    if not dt:
        return ""
    day_name = DAYS_ES[dt.weekday()]
    month_name = MONTHS_ES[dt.month - 1]
    return f"{day_name}, {dt.day} de {month_name}"

LEAGUE_NICKNAMES = {
    "bol.1": "Liga Boliviana",
    "Bolivian Liga Profesional": "Liga Boliviana",
    "eng.1": "Premier League",
    "English Premier League": "Premier League",
    "esp.1": "La Liga",
    "Spanish LALIGA": "La Liga",
    "uefa.champions": "Champions League",
    "UEFA Champions League": "Champions League"
}

def clean_league_name(raw_name, code=""):
    if code in LEAGUE_NICKNAMES:
        return LEAGUE_NICKNAMES[code]
    for k, v in LEAGUE_NICKNAMES.items():
        if k.lower() in raw_name.lower():
            return v
    return raw_name

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
            print(f"Error enviando mensaje a Telegram: {e}", flush=True)
            return False

    def format_24h_alert(self, match):
        league = escape(clean_league_name(match.get("league_name", ""), match.get("league_code", "")).upper())
        home = escape(match["home_team"].get("name", "Local"))
        away = escape(match["away_team"].get("name", "Visitante"))
        dt_local = match.get("date_local")
        date_str = format_date_es(dt_local) if dt_local else "Mañana"
        time_str = dt_local.strftime("%H:%M") if dt_local else ""
        venue = escape(match.get("venue") or "Estadio por confirmar")

        return (
            f"<b>PRÓXIMO PARTIDO · {league}</b>\n\n"
            f"<b>{home} vs {away}</b>\n\n"
            f"🗓 {date_str} a las {time_str} (Hora Bolivia)\n"
            f"📍 {venue}"
        )

    def format_1h_alert(self, match):
        league = escape(clean_league_name(match.get("league_name", ""), match.get("league_code", "")).upper())
        home = escape(match["home_team"].get("name", "Local"))
        away = escape(match["away_team"].get("name", "Visitante"))
        dt_local = match.get("date_local")
        time_str = dt_local.strftime("%H:%M") if dt_local else "En breve"
        venue = escape(match.get("venue") or "Estadio por confirmar")

        return (
            f"<b>COMIENZA EN 1 HORA · {league}</b>\n\n"
            f"<b>{home} vs {away}</b>\n\n"
            f"⏰ Hoy a las {time_str} (Hora Bolivia)\n"
            f"📍 {venue}"
        )

    def format_postmatch_recap(self, match):
        league = escape(clean_league_name(match.get("league_name", ""), match.get("league_code", "")).upper())
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
            
        msg = "<b>PRÓXIMOS PARTIDOS</b>\n\n"
        
        # Agrupar por día (fecha en hora Bolivia)
        days_dict = {}
        for m in matches:
            dt = m.get("date_local")
            if not dt:
                continue
            day_key = dt.date()
            if day_key not in days_dict:
                days_dict[day_key] = {"date": dt, "matches": []}
            days_dict[day_key]["matches"].append(m)
            
        sorted_days = sorted(days_dict.keys())
        for i, day_key in enumerate(sorted_days):
            day_info = days_dict[day_key]
            dt = day_info["date"]
            header_date = format_date_es(dt)
            msg += f"<b>{header_date}</b>\n"
            
            # Agrupar partidos por liga dentro de este día
            leagues_in_day = {}
            for m in day_info["matches"]:
                lg_clean = clean_league_name(m.get("league_name", ""), m.get("league_code", ""))
                if lg_clean not in leagues_in_day:
                    leagues_in_day[lg_clean] = []
                leagues_in_day[lg_clean].append(m)
                
            for lg_name, m_list in leagues_in_day.items():
                msg += f"\n<i>{lg_name}</i>\n"
                for m in m_list:
                    time_str = m["date_local"].strftime("%H:%M")
                    home = escape(m["home_team"].get("name", "Local"))
                    away = escape(m["away_team"].get("name", "Visitante"))
                    msg += f"• <code>{time_str}</code>  {home} vs {away}\n"
                    
            if i < len(sorted_days) - 1:
                msg += "\n"
                
        return msg.strip()
