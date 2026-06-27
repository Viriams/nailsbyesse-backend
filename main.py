from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, time, datetime, timedelta
import secrets
import cloudinary
import cloudinary.uploader
from config import settings
from database import get_conn, release_conn, init_db
from auth import (
    hash_password, verify_password,
    create_access_token, get_current_admin, init_admin
)
from emails import (
    send_confirmation_email, send_rappel_email,
    send_annulation_email, send_notif_admin
)

# ── Config Cloudinary ─────────────────────────────────────────────────────────
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Nails By Esse API",
    description="API backend pour le site Nails By Esse",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()
    await init_admin()

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class LoginSchema(BaseModel):
    email: str
    password: str

class ReservationSchema(BaseModel):
    nom: str
    prenom: str
    email: str
    telephone: str
    date: date
    heure_debut: time
    prestation_id: int
    consentement_photo: bool = False
    notes: Optional[str] = None

class StatutSchema(BaseModel):
    statut: str  # en_attente | confirme | annule

class DisponibiliteSchema(BaseModel):
    date: date
    heure_debut: time
    heure_fin: time
    bloque: bool = False
    motif_blocage: Optional[str] = None

class PrestationSchema(BaseModel):
    categorie: str
    nom: str
    prix: Optional[int] = None
    prix_texte: Optional[str] = None
    ordre: int = 0
    actif: bool = True

class GalerieUpdateSchema(BaseModel):
    categorie: Optional[str] = None
    description: Optional[str] = None
    ordre: Optional[int] = None

# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login")
async def login(data: LoginSchema):
    conn = await get_conn()
    try:
        admin = await conn.fetchrow("SELECT * FROM admins WHERE email=$1", data.email)
        if not admin or not verify_password(data.password, admin['hashed_password']):
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
        token = create_access_token({"sub": admin['email']})
        return {"access_token": token, "token_type": "bearer"}
    finally:
        await release_conn(conn)

@app.get("/api/auth/me")
async def me(admin=Depends(get_current_admin)):
    return {"email": admin['email'], "id": admin['id']}

# ─────────────────────────────────────────────────────────────────────────────
# PRESTATIONS (public + admin)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/prestations")
async def get_prestations():
    conn = await get_conn()
    try:
        rows = await conn.fetch("""
            SELECT * FROM prestations WHERE actif=TRUE ORDER BY ordre ASC
        """)
        # Grouper par catégorie
        categories = {}
        for r in rows:
            cat = r['categorie']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(dict(r))
        return {"categories": categories}
    finally:
        await release_conn(conn)

@app.post("/api/admin/prestations")
async def create_prestation(data: PrestationSchema, admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        row = await conn.fetchrow("""
            INSERT INTO prestations (categorie, nom, prix, prix_texte, ordre, actif)
            VALUES ($1,$2,$3,$4,$5,$6) RETURNING *
        """, data.categorie, data.nom, data.prix, data.prix_texte, data.ordre, data.actif)
        return dict(row)
    finally:
        await release_conn(conn)

@app.put("/api/admin/prestations/{id}")
async def update_prestation(id: int, data: PrestationSchema, admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        row = await conn.fetchrow("""
            UPDATE prestations SET categorie=$1, nom=$2, prix=$3, prix_texte=$4, ordre=$5, actif=$6
            WHERE id=$7 RETURNING *
        """, data.categorie, data.nom, data.prix, data.prix_texte, data.ordre, data.actif, id)
        if not row:
            raise HTTPException(status_code=404, detail="Prestation introuvable")
        return dict(row)
    finally:
        await release_conn(conn)

@app.delete("/api/admin/prestations/{id}")
async def delete_prestation(id: int, admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        await conn.execute("UPDATE prestations SET actif=FALSE WHERE id=$1", id)
        return {"message": "Prestation désactivée"}
    finally:
        await release_conn(conn)

# ─────────────────────────────────────────────────────────────────────────────
# DISPONIBILITÉS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/disponibilites/{date_str}")
async def get_disponibilites(date_str: str):
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de date invalide (YYYY-MM-DD)")

    # Pas de RDV le dimanche
    if d.weekday() == 6:
        return {"date": date_str, "creneaux": []}

    # Créneaux fixes de 3h : 9h-12h, 12h-15h, 15h-18h
    CRENEAUX = [
        {"heure_debut": "09:00", "heure_fin": "12:00"},
        {"heure_debut": "12:00", "heure_fin": "15:00"},
        {"heure_debut": "15:00", "heure_fin": "18:00"},
        {"heure_debut": "18:00", "heure_fin": "21:00"},

    ]

    conn = await get_conn()
    try:
        # Récupérer les jours bloqués par l'admin
        bloque = await conn.fetchrow(
            "SELECT * FROM jours_bloques WHERE date=$1", d
        )
        if bloque:
            return {"date": date_str, "creneaux": []}

        # Récupérer les réservations existantes
        reservations = await conn.fetch("""
            SELECT heure_debut FROM reservations
            WHERE date=$1 AND statut != 'annule'
        """, d)

        heures_prises = {str(r['heure_debut'])[:5] for r in reservations}

        # Filtrer les créneaux libres
        creneaux_libres = [
            c for c in CRENEAUX
            if c['heure_debut'] not in heures_prises
        ]

        return {"date": date_str, "creneaux": creneaux_libres}
    finally:
        await release_conn(conn)

@app.post("/api/admin/disponibilites")
async def create_disponibilite(data: DisponibiliteSchema, admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        row = await conn.fetchrow("""
            INSERT INTO disponibilites (date, heure_debut, heure_fin, bloque, motif_blocage)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (date, heure_debut) DO UPDATE
            SET bloque=$4, motif_blocage=$5
            RETURNING *
        """, data.date, data.heure_debut, data.heure_fin, data.bloque, data.motif_blocage)
        return dict(row)
    finally:
        await release_conn(conn)

@app.get("/api/admin/jours-bloques")
async def get_jours_bloques(admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        rows = await conn.fetch("SELECT * FROM jours_bloques ORDER BY date")
        return [dict(r) for r in rows]
    finally:
        await release_conn(conn)

@app.post("/api/admin/jours-bloques")
async def bloquer_jour(date_str: str, motif: str = "", admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        await conn.execute("""
            INSERT INTO jours_bloques (date, motif)
            VALUES ($1, $2) ON CONFLICT (date) DO NOTHING
        """, date.fromisoformat(date_str), motif)
        return {"message": "Jour bloqué"}
    finally:
        await release_conn(conn)

@app.delete("/api/admin/jours-bloques/{id}")
async def debloquer_jour(id: int, admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        await conn.execute("DELETE FROM jours_bloques WHERE id=$1", id)
        return {"message": "Jour débloqué"}
    finally:
        await release_conn(conn)

# ─────────────────────────────────────────────────────────────────────────────
# RÉSERVATIONS
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/reservations")
async def create_reservation(data: ReservationSchema, background_tasks: BackgroundTasks):
    conn = await get_conn()
    try:
        # Créneaux fixes
        CRENEAUX = {
            "09:00": "12:00",
            "12:00": "15:00",
            "15:00": "18:00",
            "18:00": "21:00",
        }

        heure_str = data.heure_debut.strftime("%H:%M")

        # Vérifier que l'heure est un créneau valide
        if heure_str not in CRENEAUX:
            raise HTTPException(status_code=400, detail="Créneau invalide")

        # Pas de RDV le dimanche
        if data.date.weekday() == 6:
            raise HTTPException(status_code=400, detail="Fermé le dimanche")

        # Vérifier jour bloqué
        bloque = await conn.fetchrow(
            "SELECT * FROM jours_bloques WHERE date=$1", data.date
        )
        if bloque:
            raise HTTPException(status_code=400, detail="Ce jour n'est pas disponible")

        # Vérifier qu'il n'y a pas déjà une réservation
        existing = await conn.fetchrow("""
            SELECT id FROM reservations
            WHERE date=$1 AND heure_debut=$2 AND statut != 'annule'
        """, data.date, data.heure_debut)
        if existing:
            raise HTTPException(status_code=400, detail="Ce créneau est déjà réservé")

        # Récupérer la prestation
        prestation = await conn.fetchrow("SELECT * FROM prestations WHERE id=$1", data.prestation_id)
        if not prestation:
            raise HTTPException(status_code=404, detail="Prestation introuvable")

        # Calculer heure_fin
        heure_fin_str = CRENEAUX[heure_str]
        heure_fin = time.fromisoformat(heure_fin_str)

        # Créer la réservation
        token = secrets.token_urlsafe(32)
        row = await conn.fetchrow("""
            INSERT INTO reservations
            (token_annulation, nom, prenom, email, telephone, date, heure_debut, heure_fin,
             prestation_id, prestation_nom, prestation_prix, consentement_photo, notes)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            RETURNING *
        """, token, data.nom, data.prenom, data.email, data.telephone,
            data.date, data.heure_debut, heure_fin,
            data.prestation_id, prestation['nom'], prestation['prix'],
            data.consentement_photo, data.notes)

        reservation = dict(row)

        # Emails en arrière-plan
        background_tasks.add_task(send_confirmation_email, reservation)
        background_tasks.add_task(send_notif_admin, reservation)

        return {
            "message": "Réservation confirmée !",
            "id": reservation['id'],
            "token": token
        }
    finally:
        await release_conn(conn)

@app.get("/api/reservations/annuler/{token}")
async def annuler_reservation(token: str, background_tasks: BackgroundTasks):
    conn = await get_conn()
    try:
        reservation = await conn.fetchrow(
            "SELECT * FROM reservations WHERE token_annulation=$1", token
        )
        if not reservation:
            raise HTTPException(status_code=404, detail="Réservation introuvable")
        if reservation['statut'] == 'annule':
            return {"message": "Cette réservation est déjà annulée"}

        await conn.execute("""
            UPDATE reservations SET statut='annule', updated_at=NOW()
            WHERE token_annulation=$1
        """, token)

        background_tasks.add_task(send_annulation_email, dict(reservation))
        return {"message": "Votre réservation a été annulée avec succès"}
    finally:
        await release_conn(conn)

@app.delete("/api/admin/reservations/{id}")
async def delete_reservation(id: int, admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        await conn.execute("DELETE FROM reservations WHERE id=$1", id)
        return {"message": "Réservation supprimée"}
    finally:
        await release_conn(conn)

@app.get("/api/admin/reservations")
async def get_reservations(
    statut: Optional[str] = None,
    date_debut: Optional[str] = None,
    date_fin: Optional[str] = None,
    admin=Depends(get_current_admin)
):
    conn = await get_conn()
    try:
        query = "SELECT * FROM reservations WHERE 1=1"
        params = []
        i = 1
        if statut:
            query += f" AND statut=${i}"; params.append(statut); i+=1
        if date_debut:
            query += f" AND date >= ${i}"; params.append(date.fromisoformat(date_debut)); i+=1
        if date_fin:
            query += f" AND date <= ${i}"; params.append(date.fromisoformat(date_fin)); i+=1
        query += " ORDER BY date DESC, heure_debut ASC"
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]
    finally:
        await release_conn(conn)

@app.patch("/api/admin/reservations/{id}/statut")
async def update_statut(id: int, data: StatutSchema, background_tasks: BackgroundTasks, admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        row = await conn.fetchrow("""
            UPDATE reservations SET statut=$1, updated_at=NOW()
            WHERE id=$2 RETURNING *
        """, data.statut, id)
        if not row:
            raise HTTPException(status_code=404, detail="Réservation introuvable")
        if data.statut == 'annule':
            background_tasks.add_task(send_annulation_email, dict(row))
        return dict(row)
    finally:
        await release_conn(conn)

@app.get("/api/admin/stats")
async def get_stats(admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        today = date.today()
        stats = {
            "aujourd_hui": await conn.fetchval(
                "SELECT COUNT(*) FROM reservations WHERE date=$1 AND statut!='annule'", today),
            "semaine": await conn.fetchval("""
                SELECT COUNT(*) FROM reservations
                WHERE date BETWEEN $1 AND $2 AND statut!='annule'
            """, today, today + timedelta(days=7)),
            "mois": await conn.fetchval("""
                SELECT COUNT(*) FROM reservations
                WHERE EXTRACT(MONTH FROM date)=EXTRACT(MONTH FROM NOW())
                AND EXTRACT(YEAR FROM date)=EXTRACT(YEAR FROM NOW())
                AND statut!='annule'
            """),
            "en_attente": await conn.fetchval(
                "SELECT COUNT(*) FROM reservations WHERE statut='en_attente'"),
            "total": await conn.fetchval("SELECT COUNT(*) FROM reservations WHERE statut!='annule'"),
        }
        return stats
    finally:
        await release_conn(conn)

# ─────────────────────────────────────────────────────────────────────────────
# GALERIE
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/galerie")
async def get_galerie(categorie: Optional[str] = None):
    conn = await get_conn()
    try:
        if categorie:
            rows = await conn.fetch(
                "SELECT * FROM galerie WHERE categorie=$1 ORDER BY ordre, created_at DESC", categorie)
        else:
            rows = await conn.fetch("SELECT * FROM galerie ORDER BY ordre, created_at DESC")
        return [dict(r) for r in rows]
    finally:
        await release_conn(conn)

@app.post("/api/admin/galerie/upload")
async def upload_photo(
    file: UploadFile = File(...),
    categorie: str = Form("Nail Art"),
    description: str = Form(""),
    admin=Depends(get_current_admin)
):
    try:
        contents = await file.read()
        result = cloudinary.uploader.upload(
            contents,
            folder="nailsbyesse",
            resource_type="image"
        )
        conn = await get_conn()
        try:
            row = await conn.fetchrow("""
                INSERT INTO galerie (url, public_id, categorie, description)
                VALUES ($1,$2,$3,$4) RETURNING *
            """, result['secure_url'], result['public_id'], categorie, description)
            return dict(row)
        finally:
            await release_conn(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur upload : {str(e)}")

@app.put("/api/admin/galerie/{id}")
async def update_galerie(id: int, data: GalerieUpdateSchema, admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        row = await conn.fetchrow("""
            UPDATE galerie SET
                categorie=COALESCE($1, categorie),
                description=COALESCE($2, description),
                ordre=COALESCE($3, ordre)
            WHERE id=$4 RETURNING *
        """, data.categorie, data.description, data.ordre, id)
        if not row:
            raise HTTPException(status_code=404, detail="Photo introuvable")
        return dict(row)
    finally:
        await release_conn(conn)

@app.delete("/api/admin/galerie/{id}")
async def delete_photo(id: int, admin=Depends(get_current_admin)):
    conn = await get_conn()
    try:
        row = await conn.fetchrow("SELECT * FROM galerie WHERE id=$1", id)
        if not row:
            raise HTTPException(status_code=404, detail="Photo introuvable")
        try:
            cloudinary.uploader.destroy(row['public_id'])
        except Exception:
            pass
        await conn.execute("DELETE FROM galerie WHERE id=$1", id)
        return {"message": "Photo supprimée"}
    finally:
        await release_conn(conn)

# ─────────────────────────────────────────────────────────────────────────────
# RAPPELS (à appeler via un cron job)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/admin/send-rappels")
async def send_rappels(background_tasks: BackgroundTasks, admin=Depends(get_current_admin)):
    """Envoie les rappels 24h avant — à appeler chaque jour via un cron"""
    conn = await get_conn()
    try:
        tomorrow = date.today() + timedelta(days=1)
        reservations = await conn.fetch("""
            SELECT * FROM reservations
            WHERE date=$1 AND statut='confirme' AND rappel_envoye=FALSE
        """, tomorrow)

        count = 0
        for r in reservations:
            background_tasks.add_task(send_rappel_email, dict(r))
            await conn.execute(
                "UPDATE reservations SET rappel_envoye=TRUE WHERE id=$1", r['id']
            )
            count += 1

        return {"message": f"{count} rappel(s) envoyé(s)"}
    finally:
        await release_conn(conn)

@app.get("/")
async def root():
    return {"message": "Nails By Esse API 💅", "version": "1.0.0", "status": "online"}
