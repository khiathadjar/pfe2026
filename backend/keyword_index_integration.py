"""
Integration des mots clés avec le CRUD existant.

Ce module fournit des hooks pour mettre à jour automatiquement l'index des mots clés
lors de la création ou modification d'objets.
"""

from backend.base import things_collection, keyword_index_collection
from backend.populate_keywords import extract_keywords_from_object, update_keyword_for_object
from pymongo import InsertOne
from typing import Optional, Dict, Any
from bson import ObjectId


def sync_keyword_index_on_create(thing_id: str, thing_data: dict) -> bool:
    """
    Appeler cette fonction après la création d'un nouvel objet.
    
    Args:
        thing_id: L'ID de l'objet créé
        thing_data: Les données de l'objet
        
    Returns:
        True si succès, False sinon
    """
    try:
        keywords_weight = extract_keywords_from_object(thing_data)
        operations = []
        
        for mot, poids in keywords_weight.items():
            doc = {
                "mot": mot,
                "thingId": thing_id,
                "poids": poids,
                "frequence": 1,
                "object_name": thing_data.get("name", ""),
            }
            operations.append(InsertOne(doc))
        
        if operations:
            keyword_index_collection.bulk_write(operations)
            print(f"✅ Index mis à jour pour l'objet {thing_id} ({len(operations)} mots)")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour de l'index: {e}")
        return False


def sync_keyword_index_on_update(thing_id: str, thing_data: dict) -> bool:
    """
    Appeler cette fonction après la modification d'un objet.
    Reconstructs tous les mots clés de cet objet.
    
    Args:
        thing_id: L'ID de l'objet modifié
        thing_data: Les nouvelles données de l'objet
        
    Returns:
        True si succès, False sinon
    """
    return update_keyword_for_object(thing_id, thing_data)


def sync_keyword_index_on_delete(thing_id: str) -> bool:
    """
    Appeler cette fonction après la suppression d'un objet.
    
    Args:
        thing_id: L'ID de l'objet supprimé
        
    Returns:
        True si succès, False sinon
    """
    try:
        result = keyword_index_collection.delete_many({"thingId": thing_id})
        print(f"🗑️  {result.deleted_count} mots clés supprimés pour l'objet {thing_id}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la suppression des mots clés: {e}")
        return False


def get_search_results_with_keywords(tokens: list[str], 
                                    limit: int = 50) -> list[Dict[str, Any]]:
    """
    Récupère les objets correspondant aux tokens avec les détails complets.
    
    Cette fonction combine:
    1. Requête sur keyword_index
    2. Calcul d'un score par objet
    3. Récupération des détails depuis things_collection
    
    Args:
        tokens: Liste de mots clés à chercher
        limit: Nombre maximum de résultats
        
    Returns:
        Liste d'objets avec scores de pertinence
    """
    if not tokens:
        return []
    
    try:
        # Étape 1: Récupérer les documents de l'index
        index_docs = list(keyword_index_collection.find({
            "mot": {"$in": tokens}
        }).limit(5000))
        
        # Étape 2: Calculer le score par objet
        score_by_thing = {}
        for doc in index_docs:
            thing_id = str(doc.get("thingId") or "").strip()
            if not thing_id:
                continue
            
            weight = int(doc.get("poids") or 1)
            freq = int(doc.get("frequence") or 1)
            score = weight * max(1, freq)
            
            score_by_thing[thing_id] = score_by_thing.get(thing_id, 0) + score
        
        # Étape 3: Récupérer les objets et ajouter le score
        results = []
        for thing_id, score in sorted(score_by_thing.items(), 
                                     key=lambda x: x[1], 
                                     reverse=True)[:limit]:
            try:
                thing = things_collection.find_one({"_id": ObjectId(thing_id)})
                if thing:
                    thing["_score"] = score  # Ajouter le score de pertinence
                    results.append(thing)
            except:
                pass
        
        return results
        
    except Exception as e:
        print(f"❌ Erreur lors de la recherche: {e}")
        return []


def bulk_rebuild_keywords(batch_size: int = 100):
    """
    Reconstruit l'index des mots clés pour TOUS les objets.
    Utile pour une maintenance complète.
    
    Args:
        batch_size: Nombre d'objets à traiter par batch
    """
    print(f"🔄 Reconstruction de l'index en cours (batch_size={batch_size})...")
    
    try:
        # Vider l'index
        keyword_index_collection.delete_many({})
        
        # Traiter les objets par batch
        total = 0
        batch = []
        
        for thing in things_collection.find({}):
            thing_id = str(thing["_id"])
            keywords_weight = extract_keywords_from_object(thing)
            
            for mot, poids in keywords_weight.items():
                doc = {
                    "mot": mot,
                    "thingId": thing_id,
                    "poids": poids,
                    "frequence": 1,
                    "object_name": thing.get("name", ""),
                }
                batch.append(InsertOne(doc))
            
            # Insérer quand le batch est plein
            if len(batch) >= batch_size * 10:  # ~1000 documents
                keyword_index_collection.bulk_write(batch)
                total += len(batch)
                print(f"  ✅ {total} documents insérés...")
                batch = []
        
        # Insérer les documents restants
        if batch:
            keyword_index_collection.bulk_write(batch)
            total += len(batch)
        
        print(f"✨ Reconstruction terminée! ({total} documents)")
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


# ============================================================================
# EXEMPLE D'INTÉGRATION DANS main_crud.py
# ============================================================================

"""
À ajouter dans main_crud.py:

from keyword_index_integration import (
    sync_keyword_index_on_create,
    sync_keyword_index_on_update,
    sync_keyword_index_on_delete
)

# Dans la route de création d'objet:
@crud_router.post("/things")
def create_thing(data: ThingCreateRequest):
    result = things_collection.insert_one(data.dict())
    thing_id = str(result.inserted_id)
    
    # ✨ Ajouter cette ligne:
    sync_keyword_index_on_create(thing_id, data.dict())
    
    return {"id": thing_id, "status": "created"}


# Dans la route de mise à jour:
@crud_router.put("/things/{thing_id}")
def update_thing(thing_id: str, data: ThingUpdateRequest):
    things_collection.update_one(
        {"_id": ObjectId(thing_id)},
        {"$set": data.dict()}
    )
    
    # ✨ Ajouter cette ligne:
    sync_keyword_index_on_update(thing_id, data.dict())
    
    return {"status": "updated"}


# Dans la route de suppression:
@crud_router.delete("/things/{thing_id}")
def delete_thing(thing_id: str):
    things_collection.delete_one({"_id": ObjectId(thing_id)})
    
    # ✨ Ajouter cette ligne:
    sync_keyword_index_on_delete(thing_id)
    
    return {"status": "deleted"}
"""

