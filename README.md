# 💅 Nails By Esse — Backend API

FastAPI + PostgreSQL (Neon) + Resend + Cloudinary

## Installation locale

```bash
pip install -r requirements.txt
cp .env.example .env
# Remplis les variables dans .env
uvicorn main:app --reload
```

## Documentation API
→ http://localhost:8000/docs (Swagger automatique)

## Variables d'environnement requises

| Variable | Description |
|---|---|
| `DATABASE_URL` | URL Neon PostgreSQL |
| `SECRET_KEY` | Clé secrète JWT (longue et aléatoire) |
| `ADMIN_EMAIL` | Email de la gérante |
| `ADMIN_PASSWORD` | Mot de passe admin |
| `RESEND_API_KEY` | Clé API Resend |
| `CLOUDINARY_CLOUD_NAME` | Nom du cloud Cloudinary |
| `CLOUDINARY_API_KEY` | Clé API Cloudinary |
| `CLOUDINARY_API_SECRET` | Secret Cloudinary |
| `FRONTEND_URL` | URL du site front-end |

## Endpoints principaux

### Public
| Route | Description |
|---|---|
| `GET /api/prestations` | Liste des services et tarifs |
| `GET /api/disponibilites/{date}` | Créneaux disponibles |
| `POST /api/reservations` | Créer une réservation |
| `GET /api/reservations/annuler/{token}` | Annuler une réservation |
| `GET /api/galerie` | Photos du catalogue |

### Admin (JWT requis)
| Route | Description |
|---|---|
| `POST /api/auth/login` | Connexion admin |
| `GET /api/admin/stats` | Statistiques |
| `GET /api/admin/reservations` | Liste des réservations |
| `PATCH /api/admin/reservations/{id}/statut` | Changer statut |
| `POST /api/admin/disponibilites` | Créer un créneau |
| `POST /api/admin/galerie/upload` | Uploader une photo |
| `PUT /api/admin/prestations/{id}` | Modifier un tarif |
| `POST /api/admin/send-rappels` | Envoyer rappels 24h |

## Déploiement Railway

```bash
git init
git add .
git commit -m "backend nailsbyesse"
git branch -M main
git remote add origin https://github.com/Viriams/nailsbyesse-backend.git
git push -u origin main
```

Puis Railway → New Project → GitHub → ajouter les variables d'env.
