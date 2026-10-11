# =============================================================================
# app.py — Dashboard Streamlit : Requêtes géospatiales MongoDB
# Projet : Requêtes géospatiales MongoDB (Master IA — NoSQL)
# =============================================================================
# Ce dashboard :
#   1. Affiche une carte Folium centrée sur le quartier Maârif (Casablanca)
#   2. Permet d'ajuster le rayon de recherche via un slider
#   3. Exécute une requête $near avec $maxDistance sur MongoDB
#   4. Affiche les livreurs trouvés sur la carte (marqueurs verts)
#   5. Trace un cercle représentant le rayon de recherche
#   6. Affiche les métriques de performance (explain) pour prouver
#      l'utilisation de l'index 2dsphere
# =============================================================================

import streamlit as st
from pymongo import MongoClient
import folium
from folium import plugins
from streamlit_folium import st_folium

# ─── Configuration ───────────────────────────────────────────────────────────
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "livraison_db"
COLLECTION_NAME = "livreurs"

# Position du client (centre de recherche) — Quartier Maârif, Casablanca
CLIENT_LON = -7.6325
CLIENT_LAT = 33.5885


# ─── Connexion MongoDB (mise en cache pour la performance) ───────────────────
@st.cache_resource
def get_mongo_collection():
    """
    Crée et met en cache la connexion MongoDB.
    st.cache_resource évite de recréer la connexion à chaque rechargement.
    """
    client = MongoClient(MONGO_URI)
    return client[DB_NAME][COLLECTION_NAME]


def rechercher_livreurs_proximite(collection, lon: float, lat: float, rayon_m: int):
    """
    Effectue une requête géospatiale $near pour trouver les livreurs
    dans un rayon donné autour d'un point.
    
    Paramètres :
        collection : collection PyMongo
        lon, lat   : coordonnées du point central (client)
        rayon_m    : rayon de recherche en mètres
    
    Retourne :
        liste des livreurs trouvés
    
    La requête utilise :
        - $near         : trie par distance croissante
        - $geometry     : spécifie le point central en GeoJSON
        - $maxDistance   : limite la recherche au rayon spécifié (en mètres)
    """
    filtre = {
        "localisation": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
                "$maxDistance": rayon_m,
            }
        }
    }
    return list(collection.find(filtre))


def obtenir_stats_performance(collection, lon: float, lat: float, rayon_m: int):
    """
    Exécute la même requête avec .explain("executionStats") pour obtenir
    les métriques de performance qui prouvent l'utilisation de l'index.
    
    Métriques clés extraites :
        - executionTimeMillis  : temps d'exécution en millisecondes
        - totalDocsExamined    : nombre de documents scannés
        - nReturned            : nombre de documents retournés
        - indexName            : nom de l'index utilisé (si IXSCAN)
        - stage                : type de scan (IXSCAN = index, COLLSCAN = scan complet)
    """
    filtre = {
        "localisation": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat],
                },
                "$maxDistance": rayon_m,
            }
        }
    }

    # On utilise db.command("explain") pour passer le niveau de verbosité
    # "executionStats", car Cursor.explain() de PyMongo ne l'accepte pas.
    db = collection.database
    explication = db.command(
        "explain",
        {"find": collection.name, "filter": filtre},
        verbosity="executionStats",
    )

    # Extraction des métriques depuis la structure de l'explain
    exec_stats = explication.get("executionStats", {})
    
    # Recherche récursive de l'étape d'input (pour trouver IXSCAN)
    stage = exec_stats.get("executionStages", {})
    index_name = "N/A"
    scan_type = stage.get("stage", "N/A")
    
    # Parcours des étapes imbriquées pour trouver l'index utilisé
    current = stage
    while current:
        if current.get("stage") == "IXSCAN":
            index_name = current.get("indexName", "N/A")
            break
        # MongoDB peut imbriquer les étapes dans "inputStage" ou "inputStages"
        if "inputStage" in current:
            current = current["inputStage"]
        elif "inputStages" in current:
            # Chercher dans toutes les sous-étapes
            found = False
            for sub in current["inputStages"]:
                if sub.get("stage") == "IXSCAN":
                    index_name = sub.get("indexName", "N/A")
                    found = True
                    break
            if found:
                break
            current = current["inputStages"][0] if current["inputStages"] else None
        else:
            break

    return {
        "execution_time_ms": exec_stats.get("executionTimeMillis", 0),
        "total_docs_examined": exec_stats.get("totalDocsExamined", 0),
        "n_returned": exec_stats.get("nReturned", 0),
        "index_name": index_name,
        "scan_type": scan_type,
        "total_keys_examined": exec_stats.get("totalKeysExamined", 0),
    }


def creer_carte(livreurs: list, rayon_m: int):
    """
    Crée une carte Folium avec :
        - Un marqueur rouge pour le client (position fixe)
        - Un cercle semi-transparent pour le rayon de recherche
        - Des marqueurs verts pour chaque livreur trouvé
    """
    # Initialisation de la carte centrée sur le client
    carte = folium.Map(
        location=[CLIENT_LAT, CLIENT_LON],
        zoom_start=15,
        tiles="CartoDB positron",
    )

    # ── Marqueur du client (rouge) ───────────────────────────────────────
    folium.Marker(
        location=[CLIENT_LAT, CLIENT_LON],
        popup=folium.Popup(
            "<b>📍 Position du Client</b><br>"
            f"Lat: {CLIENT_LAT}<br>"
            f"Lon: {CLIENT_LON}<br>"
            "<i>Quartier Maârif, Casablanca</i>",
            max_width=250,
        ),
        tooltip="🔴 Client",
        icon=folium.Icon(color="red", icon="home", prefix="fa"),
    ).add_to(carte)

    # ── Cercle du rayon de recherche ─────────────────────────────────────
    folium.Circle(
        location=[CLIENT_LAT, CLIENT_LON],
        radius=rayon_m,
        color="#3388ff",
        fill=True,
        fill_color="#3388ff",
        fill_opacity=0.1,
        weight=2,
        dash_array="5, 10",
        popup=f"Rayon : {rayon_m} m",
        tooltip=f"Rayon de recherche : {rayon_m} m",
    ).add_to(carte)

    # ── Marqueurs des livreurs (verts) ───────────────────────────────────
    # Icônes par type de véhicule
    icones_vehicules = {
        "Moto": "motorcycle",
        "Vélo": "bicycle",
        "Scooter": "motorcycle",
        "Voiture": "car",
    }

    for livreur in livreurs:
        coords = livreur["localisation"]["coordinates"]
        lat, lon = coords[1], coords[0]  # GeoJSON = [lon, lat]

        # Couleur selon le statut
        couleur = "green" if livreur["statut"] == "disponible" else (
            "orange" if livreur["statut"] == "en course" else "gray"
        )

        icone_fa = icones_vehicules.get(livreur["vehicule"], "user")

        popup_html = (
            f"<b>🛵 {livreur['nom']}</b><br>"
            f"Véhicule : {livreur['vehicule']}<br>"
            f"Statut : <b>{livreur['statut']}</b><br>"
            f"Note : {'⭐' * int(livreur['note'])} ({livreur['note']})<br>"
            f"📍 [{lon:.4f}, {lat:.4f}]"
        )

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"🟢 {livreur['nom']} ({livreur['vehicule']})",
            icon=folium.Icon(color=couleur, icon=icone_fa, prefix="fa"),
        ).add_to(carte)

    return carte


# =============================================================================
#                          APPLICATION STREAMLIT
# =============================================================================

def main():
    # ── Configuration de la page ─────────────────────────────────────────
    st.set_page_config(
        page_title="🌍 GeoSearch — Livraison MongoDB",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ── CSS personnalisé pour un rendu premium ───────────────────────────
    st.markdown("""
    <style>
        /* ── Thème général ─────────────────────────────────── */
        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
        
        /* ── En-tête ──────────────────────────────────────── */
        .header-container {
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            padding: 1.5rem 2rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        .header-title {
            color: #ffffff;
            font-size: 2rem;
            font-weight: 700;
            margin: 0;
            letter-spacing: -0.5px;
        }
        .header-subtitle {
            color: #a0aec0;
            font-size: 1rem;
            margin-top: 0.3rem;
        }
        
        /* ── Cartes métriques ─────────────────────────────── */
        .metric-card {
            background: linear-gradient(145deg, #1a1a2e, #16213e);
            padding: 1.2rem;
            border-radius: 10px;
            border-left: 4px solid;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            margin-bottom: 0.8rem;
        }
        .metric-card.green  { border-left-color: #00d2ff; }
        .metric-card.blue   { border-left-color: #7928ca; }
        .metric-card.orange { border-left-color: #ff6b6b; }
        .metric-card.purple { border-left-color: #f093fb; }
        
        .metric-label {
            color: #a0aec0;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.3rem;
        }
        .metric-value {
            color: #ffffff;
            font-size: 1.8rem;
            font-weight: 700;
        }
        .metric-detail {
            color: #718096;
            font-size: 0.75rem;
            margin-top: 0.2rem;
        }
        
        /* ── Badge de statut ──────────────────────────────── */
        .status-badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .status-disponible { background: #c6f6d5; color: #22543d; }
        .status-en-course  { background: #fefcbf; color: #744210; }
        .status-hors-ligne { background: #fed7d7; color: #9b2c2c; }
        
        /* ── Sidebar ──────────────────────────────────────── */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f0c29 0%, #1a1a2e 100%);
        }
        [data-testid="stSidebar"] .stMarkdown p,
        [data-testid="stSidebar"] .stMarkdown h1,
        [data-testid="stSidebar"] .stMarkdown h2,
        [data-testid="stSidebar"] .stMarkdown h3 {
            color: #e2e8f0;
        }
    </style>
    """, unsafe_allow_html=True)

    # ── En-tête ──────────────────────────────────────────────────────────
    st.markdown("""
    <div class="header-container">
        <p class="header-title">🌍 GeoSearch — Recherche de Livreurs</p>
        <p class="header-subtitle">
            Requêtes géospatiales MongoDB · Index 2dsphere · Quartier Maârif, Casablanca
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Connexion MongoDB ────────────────────────────────────────────────
    collection = get_mongo_collection()

    # ── Sidebar : Contrôles ──────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚙️ Paramètres de recherche")
        st.markdown("---")

        rayon = st.slider(
            "📏 Rayon de recherche (mètres)",
            min_value=500,
            max_value=5000,
            value=2000,
            step=500,
            help="Ajustez le rayon pour trouver les livreurs à proximité du client.",
        )

        st.markdown("---")
        st.markdown("### 📌 Position du Client")
        st.markdown(f"**Latitude** : `{CLIENT_LAT}`")
        st.markdown(f"**Longitude** : `{CLIENT_LON}`")
        st.markdown("**Lieu** : Quartier Maârif, Casablanca")

        st.markdown("---")
        st.markdown("### 📚 Technologies utilisées")
        st.markdown("""
        - 🍃 **MongoDB** — Base NoSQL
        - 🐍 **PyMongo** — Driver Python
        - 🌐 **Streamlit** — Interface web
        - 🗺️ **Folium** — Cartographie
        - 📐 **Index 2dsphere** — Index géospatial
        - 🔍 **$near** — Opérateur de proximité
        """)

    # ── Requête géospatiale ──────────────────────────────────────────────
    livreurs = rechercher_livreurs_proximite(collection, CLIENT_LON, CLIENT_LAT, rayon)
    stats = obtenir_stats_performance(collection, CLIENT_LON, CLIENT_LAT, rayon)

    # ── Métriques de performance (preuve de l'index) ─────────────────────
    st.markdown("### 📊 Métriques de Performance — `explain('executionStats')`")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card green">
            <div class="metric-label">Livreurs trouvés</div>
            <div class="metric-value">{stats['n_returned']}</div>
            <div class="metric-detail">nReturned</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card blue">
            <div class="metric-label">Documents examinés</div>
            <div class="metric-value">{stats['total_docs_examined']}</div>
            <div class="metric-detail">totalDocsExamined</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card orange">
            <div class="metric-label">Temps d'exécution</div>
            <div class="metric-value">{stats['execution_time_ms']} ms</div>
            <div class="metric-detail">executionTimeMillis</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card purple">
            <div class="metric-label">Clés index examinées</div>
            <div class="metric-value">{stats['total_keys_examined']}</div>
            <div class="metric-detail">totalKeysExamined</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Verdict sur l'utilisation de l'index ─────────────────────────────
    if stats["scan_type"] != "COLLSCAN":
        st.success(
            f"✅ **Index utilisé !** — Étape : `{stats['scan_type']}` · "
            f"Index : `{stats['index_name']}` · "
            f"Seulement **{stats['total_docs_examined']}** document(s) examiné(s) "
            f"au lieu de scanner toute la collection."
        )
    else:
        st.error(
            "❌ **COLLSCAN détecté !** — MongoDB a scanné toute la collection. "
            "Vérifiez que l'index 2dsphere a bien été créé via `setup_db.py`."
        )

    st.markdown("---")

    # ── Carte et tableau ─────────────────────────────────────────────────
    col_carte, col_liste = st.columns([3, 1])

    with col_carte:
        st.markdown(f"### 🗺️ Carte — Rayon de {rayon} m")
        carte = creer_carte(livreurs, rayon)
        st_folium(carte, use_container_width=True, height=550)

    with col_liste:
        st.markdown(f"### 🛵 Livreurs ({len(livreurs)})")
        
        if not livreurs:
            st.warning("Aucun livreur trouvé dans ce rayon.")
        else:
            for i, livreur in enumerate(livreurs, 1):
                # Badge de statut coloré
                statut = livreur["statut"]
                classe_statut = statut.replace(" ", "-")
                
                st.markdown(f"""
                <div style="
                    background: linear-gradient(145deg, #1e1e30, #252540);
                    padding: 0.8rem;
                    border-radius: 8px;
                    margin-bottom: 0.5rem;
                    border-left: 3px solid {'#48bb78' if statut == 'disponible' else '#ecc94b' if statut == 'en course' else '#fc8181'};
                ">
                    <div style="color: #fff; font-weight: 600;">
                        {i}. {livreur['nom']}
                    </div>
                    <div style="color: #a0aec0; font-size: 0.8rem;">
                        {livreur['vehicule']} · ⭐ {livreur['note']} ·
                        <span class="status-badge status-{classe_statut}">{statut}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # ── Footer ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #718096; font-size: 0.8rem;'>"
        "Projet Master IA — Requêtes Géospatiales MongoDB · Index 2dsphere & Opérateurs Géométriques"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
