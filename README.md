# 🌍 Requêtes Géospatiales MongoDB — Projet Master IA

> **Sujet** : Index 2dsphere et opérateurs géométriques dans MongoDB  
> **Cas d'usage** : Scénario de livraison (type Uber/Deliveroo) — recherche de livreurs par proximité

## 📸 Aperçu

Le dashboard affiche en temps réel les livreurs à proximité d'un client situé au **Quartier Maârif, Casablanca**, avec des métriques de performance prouvant l'efficacité de l'index géospatial `2dsphere`.

## 🛠️ Technologies

| Technologie | Rôle |
|-------------|------|
| **MongoDB** | Base de données NoSQL avec index géospatial 2dsphere |
| **PyMongo** | Driver Python pour MongoDB |
| **Streamlit** | Interface web interactive (dashboard) |
| **Folium** | Cartographie interactive (OpenStreetMap) |
| **streamlit-folium** | Intégration Folium ↔ Streamlit |

## 📁 Structure du projet

```
├── setup_db.py          # Script d'initialisation de la base MongoDB
├── app.py               # Dashboard Streamlit (application principale)
├── requirements.txt     # Dépendances Python
├── .gitignore           # Fichiers ignorés par Git
└── README.md            # Ce fichier
```

## 🚀 Installation & Lancement

### Prérequis
- Python 3.10+
- MongoDB en local (`mongodb://localhost:27017/`)

### 1. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 2. Initialiser la base de données
```bash
python setup_db.py
```
Ce script :
- Crée la base `livraison_db` et la collection `livreurs`
- Insère 20 livreurs fictifs avec coordonnées GeoJSON autour du Maârif
- Crée l'index `2dsphere` sur le champ `localisation`

### 3. Lancer le dashboard
```bash
streamlit run app.py
```
Le dashboard s'ouvre automatiquement à `http://localhost:8501`

## 📐 Concepts clés

### Format GeoJSON
```json
{
  "type": "Point",
  "coordinates": [-7.6325, 33.5885]
}
```
> ⚠️ GeoJSON utilise `[longitude, latitude]` (et non `[lat, lon]`)

### Requête `$near` avec `$maxDistance`
```python
{
  "localisation": {
    "$near": {
      "$geometry": {"type": "Point", "coordinates": [lon, lat]},
      "$maxDistance": rayon_metres
    }
  }
}
```

### Preuve de performance (`explain`)
Le dashboard affiche les métriques `executionStats` en temps réel :
- **nReturned** — nombre de résultats
- **totalDocsExamined** — documents scannés (≈ nReturned grâce à l'index)
- **executionTimeMillis** — temps d'exécution (~1 ms)
- **totalKeysExamined** — clés d'index consultées

## 📊 Résultats de test

| Rayon | Livreurs trouvés | Docs examinés | Temps (ms) |
|-------|-----------------|---------------|------------|
| 500m  | 1               | 2             | 1          |
| 2000m | 8               | 14            | 1-9        |
| 5000m | 20              | 20            | 1          |

✅ **L'index `localisation_2dsphere` est utilisé** — aucun Collection Scan (COLLSCAN) détecté.

## 👤 Auteur

**Oumaima EL Habti** — Master IA, NoSQL

## 📜 Licence

Ce projet est à usage académique (démonstration Master IA).
