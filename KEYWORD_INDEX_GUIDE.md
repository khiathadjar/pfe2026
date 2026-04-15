# 🔍 Index de Mots Clés MongoDB - Guide Complet

## 📌 Aperçu

La collection `keyword_index` est une **collection denormalisée d'index** conçue pour optimiser la **recherche rapide** des objets par mots clés dans votre application smart building.

### Avantages
- ⚡ **Recherche ultra-rapide**: Requêtes sub-milliseconde
- 🎯 **Pertinence**: Système de poids pour classer les résultats
- 📊 **Scalabilité**: Index optimisés pour les grandes collections
- 🔄 **Maintenance facile**: Scripts pour reconstruire/mettre à jour

---

## 🗂️ Structure de la Collection

```javascript
{
  "_id": ObjectId,           // ID auto-généré
  "mot": "ECLAIRAGE",           // Mot clé normalisé
  "thingId": "507f...",     // ID de l'objet
  "poids": 10,              // Pertinence (1-100)
  "frequence": 1,           // Nombre d'occurrences
  "object_name": "...",     // Nom de l'objet (dénormalisé)
  "created_at": Date,       // Optionnel
  "updated_at": Date        // Optionnel
}
```

### Schéma de Poids (Importance)

| Champ | Poids | Justification |
|-------|-------|---------------|
| `name` | 10 | Le nom est le plus important |
| `type` | 8 | Type d'objet très pertinent |
| `tags` | 6 | Mots clés explicites |
| `room` | 5 | Localisation importante |
| `description` | 3 | Contexte additionnel |
| `status` | 2 | Moins pertinent |

---

## 🚀 Guide de Configuration

### Étape 1: Créer les Index MongoDB

```bash
# Activer l'environnement virtuel
source .venv/bin/activate  # ou sur Windows: .venv\Scripts\activate

# Créer les 6 index d'optimisation
python create_keyword_indexes.py create
```

**Index créés:**
1. `idx_mot` - Recherche simple par mot
2. `idx_mot_thingId` - Recherche avec filtrage par objet
3. `idx_thingId` - Retrouver les mots d'un objet
4. `idx_poids` - Trier par pertinence
5. `idx_mot_text` - Recherche textuelle avancée
6. `idx_mot_poids` - Recherche avec tri par pertinence

### Étape 2: Peupler la Collection

```bash
# Reconstruire l'index depuis zéro
python populate_keywords.py rebuild

# Afficher les statistiques
python populate_keywords.py stats
```

---

## 🔎 Exemples de Requêtes

### 1. Recherche Simple par Mot

```python
# Chercher tous les objets contenant le mot "ECLAIRAGE"
results = keyword_index_collection.find(
    {"mot": "ECLAIRAGE"}
).limit(10)

for doc in results:
    print(f"Objet: {doc['object_name']}, Pertinence: {doc['poids']}")
```

### 2. Recherche avec Tri par Pertinence

```python
# Trouver "ECLAIRAGE" et trier par pertinence décroissante
results = keyword_index_collection.find(
    {"mot": "ECLAIRAGE"}
).sort([("poids", -1)]).limit(20)
```

### 3. Recherche Multi-Mots

```python
# Chercher les objets contenant PLUSIEURS mots clés
from collections import Counter

mots = ["ECLAIRAGE", "bureau", "led"]
query = {"mot": {"$in": mots}}

# Agréger par thingId et compter les occurrences
pipeline = [
    {"$match": query},
    {"$group": {
        "_id": "$thingId",
        "count": {"$sum": 1},
        "total_poids": {"$sum": "$poids"},
        "object_name": {"$first": "$object_name"},
        "mots": {"$push": "$mot"}
    }},
    {"$sort": {"total_poids": -1}},
    {"$limit": 20}
]

results = keyword_index_collection.aggregate(pipeline)
```

### 4. Recherche Textuelle (Fuzzy)

```python
# Recherche textuelle avec index text
results = keyword_index_collection.find(
    {"$text": {"$search": "ECLAIRAGE bureau"}},
    {"score": {"$meta": "textScore"}}
).sort([("score", {"$meta": "textScore"})])
```

### 5. Autocomplétion

```python
# Suggestions pour l'autocomplétion
prefix = "lam"  # L'utilisateur tape "lam"

# Utiliser regex pour les suggestions
suggestions = keyword_index_collection.distinct(
    "mot",
    {"mot": {"$regex": f"^{re.escape(prefix)}", "$options": "i"}}
)
print(suggestions)  # ["ECLAIRAGE", "lambda", ...]
```

### 6. Récupérer tous les mots d'un objet

```python
# Afficher tous les mots clés d'un objet
thing_id = "507f1f77bcf86cd799439011"

words = keyword_index_collection.find(
    {"thingId": thing_id}
).sort([("poids", -1)])

for doc in words:
    print(f"{doc['mot']} (poids: {doc['poids']})")
```

---

## 🔧 Intégration avec main_recherche.py

Votre code utilise déjà cet index:

```python
def _collect_index_scores(tokens: list[str]) -> dict[str, int]:
    """Récupère les scores des objets pour les tokens."""
    docs = list(keyword_index_collection.find({
        "mot": {"$in": tokens}
    }).limit(5000))
    
    score_by_thing = {}
    for doc in docs:
        thing_id = str(doc.get("thingId") or "").strip()
        if not thing_id:
            continue
        weight = int(doc.get("poids") or 1)
        freq = int(doc.get("frequence") or 1)
        score_by_thing[thing_id] = score_by_thing.get(thing_id, 0) + (weight * max(1, freq))
    
    return score_by_thing
```

---

## 🔄 Maintenance

### Mettre à Jour un Objet

```python
from populate_keywords import update_keyword_for_object

# Quand un objet est modifié
thing_id = "507f1f77bcf86cd799439011"
thing_data = things_collection.find_one({"_id": ObjectId(thing_id)})

update_keyword_for_object(thing_id, thing_data)
```

### Reconstruire Complètement

```bash
python populate_keywords.py rebuild
```

### Afficher les Statistiques

```bash
python populate_keywords.py stats
```

### Analyser les Index

```bash
python create_keyword_indexes.py analyze
```

---

## 📊 Performance

### Complexité des Requêtes

| Requête | Index | Temps |
|---------|-------|-------|
| Trovuer par mot | `idx_mot` | 💚 O(log n) |
| + Trier par poids | `idx_mot_poids` | 💚 O(log n) |
| Multi-mots agrégés | `idx_mot` + pipeline | 💛 O(n) |
| Recherche textuelle | `idx_mot_text` | 💛 O(n) |

### Recommandations

✅ **DO:**
- Utiliser `idx_mot` ou `idx_mot_poids` pour les requêtes simples
- Agréger par `thingId` pour les résultats par objet
- Limiter `.limit(1000)` pour éviter surcharger la mémoire
- Indexer les champs régulièrement accédés

❌ **DON'T:**
- Faire des requêtes sans limite
- Faire des recherches sur des champs non-indexés
- Oublier de mettre à jour après une modification d'objet

---

## 🐛 Dépannage

### Les résultats ne s'affichent pas après ajout d'un objet?

1. Vérifier que le nouvel objet est dans `things_collection`
2. Reconstruire l'index: `python populate_keywords.py rebuild`
3. Vérifier les stats: `python populate_keywords.py stats`

### Les recherches sont lentes?

1. Vérifier que les index existent: `python create_keyword_indexes.py analyze`
2. Regénérer les index: 
   ```bash
   python create_keyword_indexes.py drop
   python create_keyword_indexes.py create
   ```
3. Vérifier la taille de la collection (comment c'est devenu trop grand?)

### Un mot clé n'apparaît pas?

1. Vérifier la normalisation: `normalize_text("Votre texte")`
2. Vérifier les règles de tokenization (min 3 caractères)
3. Vérifier le poids du champ d'origine

---

## 📈 Collection Attendue

Après `populate_keywords.py rebuild`, vous devriez avoir:

```
• ~1000-5000 mots clés uniques (selon le nombre d'objets)
• 1 entrée par (objet, mot clé)
• Taille: ~50KB - 1MB en moyenne
```

---

## 🎯 Intégration dans le Code

### Integration avec FastAPI

```python
from fastapi import APIRouter, Query

@app.get("/api/keywords/suggest")
def suggest_keywords(q: str = Query(..., min_length=2)):
    """Autocomplétion pour les mots clés."""
    suggestions = keyword_index_collection.distinct(
        "mot",
        {"mot": {"$regex": f"^{normalize_text(q)}", "$options": "i"}}
    )
    return suggestions[:10]
```

### Hook CRUD

```python
# À ajouter dans main_crud.py après chaque création/modification

def create_thing(thing_data: dict):
    result = things_collection.insert_one(thing_data)
    thing_id = str(result.inserted_id)
    
    # Mettre à jour l'index
    update_keyword_for_object(thing_id, thing_data)
    
    return thing_id
```

---

## 📚 Ressources

- Schéma JSON: [KEYWORD_INDEX_SCHEMA.json](KEYWORD_INDEX_SCHEMA.json)
- Script de création d'index: [create_keyword_indexes.py](create_keyword_indexes.py)
- Script de peuplement: [populate_keywords.py](populate_keywords.py)
- Code de recherche: [main_recherche.py](main_recherche.py)

---

**Dernière mise à jour**: April 2024

