# =============================================================================
# setup_db.py — Script d'initialisation de la base MongoDB géospatiale
# Projet : Requêtes géospatiales MongoDB (Master IA — NoSQL)
# =============================================================================
# Ce script :
#   1. Se connecte à MongoDB en local (mongodb://localhost:27017/)
#   2. Vide la collection "livreurs" si elle existe
#   3. Génère 20 livreurs fictifs autour du quartier Maârif, Casablanca
#   4. Insère les documents avec des coordonnées GeoJSON (type "Point")
#   5. Crée un index 2dsphere sur le champ "localisation"
# =============================================================================

import random
from pymongo import MongoClient, GEOSPHERE
from datetime import datetime

# ─── Configuration ───────────────────────────────────────────────────────────
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "livraison_db"
COLLECTION_NAME = "livreurs"

# Centre de référence : Quartier Maârif, Casablanca
CENTER_LON = -7.6325
CENTER_LAT = 33.5885

# ─── Données fictives ───────────────────────────────────────────────────────
PRENOMS = [
    "Youssef", "Fatima", "Omar", "Salma", "Amine",
    "Nadia", "Karim", "Hajar", "Mehdi", "Laila",
    "Rachid", "Sanaa", "Hamza", "Imane", "Bilal",
    "Kenza", "Soufiane", "Meriem", "Ayoub", "Zineb",
]

VEHICULES = ["Moto", "Vélo", "Scooter", "Voiture"]
STATUTS = ["disponible", "en course", "hors ligne"]


def generer_coordonnees_aleatoires(
    center_lon: float,
    center_lat: float,
    rayon_max_deg: float = 0.025,
) -> dict:
    """
    Génère un point GeoJSON aléatoire autour d'un centre donné.
    
    Le rayon_max_deg de 0.025° ≈ ~2.5 km, ce qui couvre bien le quartier
    Maârif et ses alentours pour une démonstration réaliste.
    
    IMPORTANT — Format GeoJSON :
        Les coordonnées sont [longitude, latitude] (et non [lat, lon]).
        C'est une exigence de la spécification GeoJSON et de MongoDB.
    """
    lon = center_lon + random.uniform(-rayon_max_deg, rayon_max_deg)
    lat = center_lat + random.uniform(-rayon_max_deg, rayon_max_deg)
    return {
        "type": "Point",
        "coordinates": [round(lon, 6), round(lat, 6)],
    }


def generer_livreurs(n: int = 20) -> list[dict]:
    """
    Génère une liste de N documents livreurs avec :
      - nom          : prénom du livreur
      - vehicule     : type de véhicule utilisé
      - statut       : disponibilité actuelle
      - note         : note moyenne (1.0 à 5.0)
      - localisation : point GeoJSON {type: "Point", coordinates: [lon, lat]}
      - cree_le      : horodatage de création
    """
    livreurs = []
    for i in range(n):
        livreur = {
            "nom": PRENOMS[i % len(PRENOMS)],
            "vehicule": random.choice(VEHICULES),
            "statut": random.choice(STATUTS),
            "note": round(random.uniform(3.0, 5.0), 1),
            "localisation": generer_coordonnees_aleatoires(CENTER_LON, CENTER_LAT),
            "cree_le": datetime.now(),
        }
        livreurs.append(livreur)
    return livreurs


def main():
    # ── 1. Connexion à MongoDB ───────────────────────────────────────────
    print("🔌 Connexion à MongoDB...")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    print(f"   ✅ Connecté à {MONGO_URI} — base : {DB_NAME}")

    # ── 2. Nettoyage de la collection existante ──────────────────────────
    nb_existants = collection.count_documents({})
    if nb_existants > 0:
        print(f"🧹 Suppression de {nb_existants} document(s) existant(s)...")
        collection.delete_many({})
        print("   ✅ Collection vidée.")
    else:
        print("📭 Collection vide, rien à supprimer.")

    # ── 3. Suppression des index existants (sauf _id) ────────────────────
    print("🗑️  Suppression des anciens index...")
    collection.drop_indexes()
    print("   ✅ Index supprimés.")

    # ── 4. Génération et insertion des livreurs ──────────────────────────
    livreurs = generer_livreurs(20)
    print(f"📦 Insertion de {len(livreurs)} livreurs...")
    result = collection.insert_many(livreurs)
    print(f"   ✅ {len(result.inserted_ids)} livreurs insérés avec succès.")

    # ── 5. Création de l'index géospatial 2dsphere ───────────────────────
    #
    #   C'est l'étape CRUCIALE du projet. L'index 2dsphere permet à MongoDB
    #   d'effectuer des recherches géospatiales efficaces (requêtes $near,
    #   $geoWithin, $geoIntersects) sans scanner toute la collection.
    #
    #   Sans cet index, une requête $near échouerait avec l'erreur :
    #       "error processing query: ns=livraison_db.livreurs
    #        planner returned error :: caused by :: unable to find index
    #        for $geoNear query"
    #
    print("🌍 Création de l'index 2dsphere sur 'localisation'...")
    index_name = collection.create_index([("localisation", GEOSPHERE)])
    print(f"   ✅ Index créé : {index_name}")

    # ── 6. Vérification finale ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DE L'INITIALISATION")
    print("=" * 60)
    print(f"   Base de données  : {DB_NAME}")
    print(f"   Collection       : {COLLECTION_NAME}")
    print(f"   Documents        : {collection.count_documents({})}")
    print(f"   Index actifs     :")
    for idx in collection.list_indexes():
        print(f"      • {idx['name']} → {dict(idx['key'])}")
    print("=" * 60)

    # Affichage d'un échantillon pour vérification
    print("\n📍 Échantillon de 3 livreurs insérés :")
    for doc in collection.find().limit(3):
        coords = doc["localisation"]["coordinates"]
        print(
            f"   • {doc['nom']:10s} | {doc['vehicule']:8s} | "
            f"{doc['statut']:12s} | ⭐ {doc['note']} | "
            f"📍 [{coords[0]}, {coords[1]}]"
        )

    client.close()
    print("\n🎉 Initialisation terminée avec succès !")


if __name__ == "__main__":
    main()
