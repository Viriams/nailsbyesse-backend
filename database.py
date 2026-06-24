import asyncpg
from config import settings

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        url = settings.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        _pool = await asyncpg.create_pool(url, min_size=1, max_size=10)
    return _pool

async def get_conn():
    pool = await get_pool()
    return await pool.acquire()

async def release_conn(conn):
    pool = await get_pool()
    await pool.release(conn)

async def init_db():
    conn = await get_conn()
    try:
        # Table admin
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                email VARCHAR(200) UNIQUE NOT NULL,
                hashed_password VARCHAR(200) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Table prestations
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS prestations (
                id SERIAL PRIMARY KEY,
                categorie VARCHAR(100) NOT NULL,
                nom VARCHAR(200) NOT NULL,
                prix INTEGER,
                prix_texte VARCHAR(50),
                ordre INTEGER DEFAULT 0,
                actif BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Table disponibilités (créneaux ouverts par la gérante)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS disponibilites (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                heure_debut TIME NOT NULL,
                heure_fin TIME NOT NULL,
                bloque BOOLEAN DEFAULT FALSE,
                motif_blocage VARCHAR(200),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(date, heure_debut)
            )
        """)

        # Table réservations
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id SERIAL PRIMARY KEY,
                token_annulation VARCHAR(100) UNIQUE NOT NULL,
                nom VARCHAR(100) NOT NULL,
                prenom VARCHAR(100) NOT NULL,
                email VARCHAR(200) NOT NULL,
                telephone VARCHAR(30) NOT NULL,
                date DATE NOT NULL,
                heure_debut TIME NOT NULL,
                heure_fin TIME NOT NULL,
                prestation_id INTEGER REFERENCES prestations(id),
                prestation_nom VARCHAR(200),
                prestation_prix INTEGER,
                consentement_photo BOOLEAN DEFAULT FALSE,
                statut VARCHAR(20) DEFAULT 'en_attente',
                notes VARCHAR(500),
                rappel_envoye BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Table galerie
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS galerie (
                id SERIAL PRIMARY KEY,
                url VARCHAR(500) NOT NULL,
                public_id VARCHAR(200) NOT NULL,
                categorie VARCHAR(100) DEFAULT 'Nail Art',
                description VARCHAR(200),
                ordre INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Insérer les prestations officielles si la table est vide
        count = await conn.fetchval("SELECT COUNT(*) FROM prestations")
        if count == 0:
            prestations = [
                # Pose semi-permanente
                ("Pose semi-permanente", "French simple", 2500, None, 1),
                ("Pose semi-permanente", "Nail art +", 4000, None, 2),
                ("Pose semi-permanente", "Nail art ++", 5000, None, 3),
                # Pose américaine
                ("Pose américaine", "French simple", 3000, None, 4),
                ("Pose américaine", "Nail art +", 4500, None, 5),
                ("Pose américaine", "Nail art ++", 5500, None, 6),
                # Autres services
                ("Autres services", "Pose en Poly gel", 6000, None, 7),
                ("Autres services", "Pose gel", 7000, None, 8),
                ("Autres services", "Dépose", 2000, None, 9),
                ("Autres services", "Press on Hand", 3500, None, 10),
                ("Autres services", "Press on Foot", 2000, None, 11),
                ("Autres services", "Manicure & Pédicure", None, "Sur devis", 12),
            ]
            await conn.executemany("""
                INSERT INTO prestations (categorie, nom, prix, prix_texte, ordre)
                VALUES ($1, $2, $3, $4, $5)
            """, prestations)

        print("✅ Base de données initialisée avec succès")
    finally:
        await release_conn(conn)
