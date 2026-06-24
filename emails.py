import resend
from config import settings
from datetime import date, time

resend.api_key = settings.RESEND_API_KEY

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS  = ["janvier", "février", "mars", "avril", "mai", "juin",
         "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

def format_date(d: date) -> str:
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month-1]} {d.year}"

def format_heure(t: time) -> str:
    return t.strftime("%H:%M")

def base_email(titre: str, contenu: str) -> str:
    return f"""
    <div style="font-family: 'Georgia', serif; max-width: 580px; margin: 0 auto; background: #1a1a1a; color: #f5f5f5; border-radius: 12px; overflow: hidden;">
      <div style="background: linear-gradient(135deg, #C2185B, #4A148C); padding: 2rem; text-align: center;">
        <h1 style="font-family: 'Georgia', serif; color: #F9A825; font-size: 1.6rem; margin: 0; letter-spacing: 0.15em;">NAILS BY ESSE</h1>
        <p style="color: rgba(255,255,255,0.7); font-size: 0.8rem; margin: 0.4rem 0 0; letter-spacing: 0.2em;">IT'S ALL ABOUT YOUR NAILS</p>
      </div>
      <div style="padding: 2rem 1.5rem;">
        <h2 style="color: #F9A825; font-size: 1.1rem; margin-bottom: 1rem;">{titre}</h2>
        {contenu}
      </div>
      <div style="background: rgba(255,255,255,0.05); padding: 1rem 1.5rem; text-align: center; font-size: 0.75rem; color: rgba(255,255,255,0.4);">
        <p>📍 Calavi, Bénin &nbsp;|&nbsp; 📱 +229 01 52 40 70 01 &nbsp;|&nbsp; @nail_sbyesse</p>
      </div>
    </div>
    """

async def send_confirmation_email(reservation: dict):
    """Email de confirmation envoyé à la cliente après réservation"""
    date_str   = format_date(reservation['date'])
    heure_str  = format_heure(reservation['heure_debut'])
    cancel_url = f"{settings.FRONTEND_URL}/annuler/{reservation['token_annulation']}"

    contenu = f"""
    <p style="color: #f5f5f5; line-height: 1.7;">
      Bonjour <strong style="color: #F9A825;">{reservation['prenom']}</strong> 💅<br><br>
      Votre réservation chez <strong>Nails By Esse</strong> est bien enregistrée !
    </p>
    <div style="background: rgba(255,255,255,0.06); border-left: 3px solid #C2185B; border-radius: 6px; padding: 1rem 1.2rem; margin: 1.2rem 0;">
      <p style="margin: 0.3rem 0; color: #f5f5f5;">📅 <strong>Date :</strong> {date_str}</p>
      <p style="margin: 0.3rem 0; color: #f5f5f5;">⏰ <strong>Heure :</strong> {heure_str}</p>
      <p style="margin: 0.3rem 0; color: #f5f5f5;">💅 <strong>Prestation :</strong> {reservation['prestation_nom']}</p>
      <p style="margin: 0.3rem 0; color: #F9A825;">💰 <strong>Tarif :</strong> {reservation['prestation_prix']:,} FCFA</p>
    </div>
    <p style="color: #f5f5f5; font-size: 0.9rem; line-height: 1.6;">
      ⚠️ Merci d'arriver à l'heure. Tout retard de plus de <strong>30 minutes</strong> entraîne l'annulation automatique du rendez-vous.
    </p>
    <p style="color: #f5f5f5; font-size: 0.9rem; margin-top: 1rem;">
      Besoin d'annuler ?
      <a href="{cancel_url}" style="color: #C2185B;">Cliquez ici pour annuler votre rendez-vous</a>
    </p>
    <p style="color: rgba(255,255,255,0.5); font-size: 0.8rem; margin-top: 1.5rem;">
      À très bientôt ✨<br>
      <strong style="color: #F9A825;">Viridiana — Nails By Esse</strong>
    </p>
    """
    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": reservation['email'],
            "subject": f"✅ Confirmation RDV — {date_str} à {heure_str}",
            "html": base_email("Votre rendez-vous est confirmé !", contenu)
        })
    except Exception as e:
        print(f"Erreur email confirmation : {e}")

async def send_rappel_email(reservation: dict):
    """Rappel 24h avant le RDV"""
    date_str  = format_date(reservation['date'])
    heure_str = format_heure(reservation['heure_debut'])
    cancel_url = f"{settings.FRONTEND_URL}/annuler/{reservation['token_annulation']}"

    contenu = f"""
    <p style="color: #f5f5f5; line-height: 1.7;">
      Bonjour <strong style="color: #F9A825;">{reservation['prenom']}</strong> 💅<br><br>
      C'est votre rappel ! Vous avez un rendez-vous <strong>demain</strong> chez Nails By Esse.
    </p>
    <div style="background: rgba(255,255,255,0.06); border-left: 3px solid #F9A825; border-radius: 6px; padding: 1rem 1.2rem; margin: 1.2rem 0;">
      <p style="margin: 0.3rem 0; color: #f5f5f5;">📅 <strong>Date :</strong> {date_str}</p>
      <p style="margin: 0.3rem 0; color: #f5f5f5;">⏰ <strong>Heure :</strong> {heure_str}</p>
      <p style="margin: 0.3rem 0; color: #f5f5f5;">💅 <strong>Prestation :</strong> {reservation['prestation_nom']}</p>
    </div>
    <p style="color: #f5f5f5; font-size: 0.9rem;">
      Si vous ne pouvez plus venir :
      <a href="{cancel_url}" style="color: #C2185B;">Annuler mon rendez-vous</a>
    </p>
    <p style="color: rgba(255,255,255,0.5); font-size: 0.8rem; margin-top: 1.5rem;">
      À demain ! ✨<br>
      <strong style="color: #F9A825;">Viridiana — Nails By Esse</strong>
    </p>
    """
    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": reservation['email'],
            "subject": f"⏰ Rappel RDV demain — {heure_str}",
            "html": base_email("Rappel : votre rendez-vous est demain !", contenu)
        })
    except Exception as e:
        print(f"Erreur email rappel : {e}")

async def send_annulation_email(reservation: dict):
    """Email d'annulation"""
    date_str  = format_date(reservation['date'])
    heure_str = format_heure(reservation['heure_debut'])

    contenu = f"""
    <p style="color: #f5f5f5; line-height: 1.7;">
      Bonjour <strong style="color: #F9A825;">{reservation['prenom']}</strong>,<br><br>
      Votre rendez-vous du <strong>{date_str} à {heure_str}</strong> a bien été annulé.
    </p>
    <p style="color: #f5f5f5; font-size: 0.9rem; line-height: 1.6;">
      Vous souhaitez reprendre un rendez-vous ?
      <a href="{settings.FRONTEND_URL}/reservation" style="color: #C2185B;">Réserver en ligne</a>
    </p>
    <p style="color: rgba(255,255,255,0.5); font-size: 0.8rem; margin-top: 1.5rem;">
      À bientôt ✨<br>
      <strong style="color: #F9A825;">Viridiana — Nails By Esse</strong>
    </p>
    """
    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": reservation['email'],
            "subject": "❌ Annulation de votre rendez-vous",
            "html": base_email("Votre rendez-vous a été annulé", contenu)
        })
    except Exception as e:
        print(f"Erreur email annulation : {e}")

async def send_notif_admin(reservation: dict):
    """Notification à la gérante pour chaque nouvelle réservation"""
    date_str  = format_date(reservation['date'])
    heure_str = format_heure(reservation['heure_debut'])

    contenu = f"""
    <p style="color: #f5f5f5;">Nouvelle réservation reçue !</p>
    <div style="background: rgba(255,255,255,0.06); border-radius: 6px; padding: 1rem 1.2rem; margin: 1rem 0;">
      <p style="margin: 0.3rem 0; color: #f5f5f5;">👤 <strong>{reservation['prenom']} {reservation['nom']}</strong></p>
      <p style="margin: 0.3rem 0; color: #f5f5f5;">📱 {reservation['telephone']}</p>
      <p style="margin: 0.3rem 0; color: #f5f5f5;">📧 {reservation['email']}</p>
      <p style="margin: 0.3rem 0; color: #f5f5f5;">📅 {date_str} à {heure_str}</p>
      <p style="margin: 0.3rem 0; color: #F9A825;">💅 {reservation['prestation_nom']} — {reservation['prestation_prix']:,} FCFA</p>
    </div>
    <a href="{settings.FRONTEND_URL}/admin/reservations" style="background: #C2185B; color: white; padding: 0.6rem 1.2rem; border-radius: 6px; text-decoration: none; font-size: 0.85rem;">
      Voir dans l'admin →
    </a>
    """
    try:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": settings.ADMIN_EMAIL,
            "subject": f"🆕 Nouvelle réservation — {reservation['prenom']} {reservation['nom']}",
            "html": base_email("Nouvelle réservation !", contenu)
        })
    except Exception as e:
        print(f"Erreur notif admin : {e}")
