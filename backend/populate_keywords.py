"""
Script pour peupler et maintenir la collection keyword_index
avec les mots clés extraits des objets (things).

Utilise une stratégie de tokenization et de poids pour optimiser la recherche.
"""

from backend.base import things_collection, keyword_index_collection
from backend.routers.main_localisation import normalize_text
from pymongo import InsertOne
from collections import Counter
import re


def tokenize_text(text: str) -> list[str]:
    """Tokenize le texte en mots (avec repetitions pour conserver la frequence)."""
    if not text:
        return []

    text = normalize_text(text)
    tokens = re.findall(r"[a-z0-9]+", text)
    return [t for t in tokens if 2 <= len(t) <= 50]


def _to_index_id(thing_id: str) -> int:
    """ConvertirIdentifiant(objet.id) vers un entier stable."""
    try:
        return int((thing_id or "").replace("-", "")[:8], 16)
    except Exception:
        return 0


def _build_index_docs_for_object(obj: dict) -> list[dict]:
    """Construit les documents keyword_index selon l'algo (mot, source, frequence)."""
    thing_id = str(obj.get("id") or "").strip()
    if not thing_id:
        return []

    champs_indexables = [
        (str(obj.get("name") or ""), "TITRE", 3),
        (str(obj.get("type") or ""), "TYPE", 2),
        (str(obj.get("description") or ""), "DESCRIPTION", 1),
        (str((obj.get("location") or {}).get("room") or "") if isinstance(obj.get("location"), dict) else "", "SALLE", 2),
    ]

    table_frequences: dict[tuple[str, str], dict[str, int]] = {}

    for valeur, source, poids_base in champs_indexables:
        valeur_norm = normalize_text(valeur)
        liste_mots = tokenize_text(valeur_norm)

        for mot in liste_mots:
            key = (mot, source)
            if key in table_frequences:
                table_frequences[key]["frequence"] += 1
            else:
                table_frequences[key] = {"poids": poids_base, "frequence": 1}

    docs = []
    for (mot, source), values in table_frequences.items():
        docs.append(
            {
                "mot": mot,
                "thingId": thing_id,
                "poids": int(values["poids"]),
                "source": source,
                "frequence": int(values["frequence"]),
            }
        )

    return docs


def extract_keywords_from_object(obj: dict) -> dict[str, int]:
    """Compat: retourne un map mot->poids max (non utilise par l'algo principal)."""
    res: dict[str, int] = {}
    for doc in _build_index_docs_for_object(obj):
        mot = str(doc.get("mot") or "")
        poids = int(doc.get("poids") or 0)
        if mot:
            res[mot] = max(res.get(mot, 0), poids)
    return res


def rebuild_keyword_index():
    """Reconstruit l'index des mots clés à partir de zéro."""
    print("🔄 Reconstruction de l'index des mots clés...")
    
    try:
        # Récupérer tous les objets
        things = list(things_collection.find({}))
        print(f"  📦 {len(things)} objets à traiter")
        
        # Préparer les opérations d'insertion
        operations = []
        keyword_stats = Counter()
        
        for thing in things:
            thing_id = str(thing.get("id") or "").strip()
            if not thing_id:
                continue

            # Aligne exactement l'algo: supprimer l'ancien index pour cet objet puis recalculer.
            keyword_index_collection.delete_many({"thingId": thing_id})

            docs = _build_index_docs_for_object(thing)
            for doc in docs:
                keyword_stats[str(doc.get("mot") or "")] += 1
                operations.append(InsertOne(doc))
        
        # Exécuter les insertions par batch
        if operations:
            print(f"  ✍️  Insertion de {len(operations)} documents...")
            result = keyword_index_collection.bulk_write(operations)
            print(f"  ✅ {result.inserted_count} documents insérés")
        
        print(f"\n📊 Statistiques des mots clés:")
        print(f"  • Nombre de mots clés uniques: {len(keyword_stats)}")
        print(f"  • Nombre total d'entrées: {len(operations)}")
        print(f"  • Top 10 mots clés:")
        for mot, count in keyword_stats.most_common(10):
            print(f"    - '{mot}': {count} fois")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return False


def update_keyword_for_object(thing_id: str, thing_data: dict):
    """Met à jour les mots clés pour un objet spécifique."""
    print(f"🔄 Mise à jour des mots clés pour l'objet: {thing_id}")
    
    try:
        # Supprimer les anciens mots clés
        deleted = keyword_index_collection.delete_many({"thingId": thing_id})
        print(f"  🗑️  {deleted.deleted_count} anciens mots clés supprimés")
        
        # Extraire et insérer les nouveaux
        thing_data = dict(thing_data or {})
        thing_data["id"] = thing_id
        docs = _build_index_docs_for_object(thing_data)
        operations = []

        for doc in docs:
            operations.append(InsertOne(doc))
        
        if operations:
            result = keyword_index_collection.bulk_write(operations)
            print(f"  ✅ {result.inserted_count} nouveaux mots clés insérés")
        else:
            print("  ℹ️  Aucun mot clé à insérer")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False


def get_index_statistics():
    """Affiche les statistiques de l'index des mots clés."""
    print("\n📊 Statistiques de l'index des mots clés:\n")
    
    try:
        total_docs = keyword_index_collection.count_documents({})
        unique_keywords = keyword_index_collection.distinct("mot")
        unique_things = keyword_index_collection.distinct("thingId")
        
        print(f"  📈 Nombre total d'entrées: {total_docs}")
        print(f"  🏷️  Nombre de mots clés uniques: {len(unique_keywords)}")
        print(f"  📦 Nombre d'objets indexés: {len(unique_things)}")
        
        # Top 15 mots clés
        top_keywords = list(keyword_index_collection.aggregate([
            {"$group": {"_id": "$mot", "count": {"$sum": 1}, "avg_poids": {"$avg": "$poids"}}},
            {"$sort": {"count": -1}},
            {"$limit": 15}
        ]))
        
        print(f"\n  🔝 Top 15 mots clés les plus fréquents:")
        for i, item in enumerate(top_keywords, 1):
            print(f"     {i}. '{item['_id']}': {item['count']} fois (poids moyen: {item['avg_poids']:.1f})")
        
        # Objets avec le plus de mots clés
        top_things = list(keyword_index_collection.aggregate([
            {"$group": {"_id": "$thingId", "count": {"$sum": 1}, "name": {"$first": "$object_name"}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]))
        
        print(f"\n  🎯 Top 10 objets avec le plus de mots clés:")
        for i, item in enumerate(top_things, 1):
            print(f"     {i}. '{item['name']}': {item['count']} mots clés")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "rebuild":
            rebuild_keyword_index()
        elif command == "stats":
            get_index_statistics()
        else:
            print(f"Commande inconnue: {command}")
            print("Commandes disponibles: rebuild, stats")
    else:
        print("Commandes disponibles:")
        print("  python populate_keywords.py rebuild  - Reconstruire l'index")
        print("  python populate_keywords.py stats    - Afficher les statistiques")

