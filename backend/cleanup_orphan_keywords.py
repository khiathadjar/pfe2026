#!/usr/bin/env python3
"""
Script pour nettoyer les mots-clés orphelins de la collection keyword_index.
Usage: python cleanup_orphan_keywords.py
"""

from backend.base import things_collection, keyword_index_collection


def cleanup_orphans():
    """Supprime tous les mots-clés dont le thingId n'existe plus dans things."""
    
    print("🔍 Analyse des mots-clés orphelins...")
    
    # Récupérer tous les thingId uniques dans keyword_index
    all_keyword_thing_ids = list(keyword_index_collection.distinct("thingId"))
    print(f"   Total des thingId uniques dans keyword_index: {len(all_keyword_thing_ids)}")
    
    # Récupérer tous les thingId uniques dans things
    all_things_ids = list(things_collection.distinct("id"))
    print(f"   Total des objets dans things: {len(all_things_ids)}")
    
    # Trouver les orphelins
    orphan_thing_ids = []
    for thing_id in all_keyword_thing_ids:
        thing_id_clean = str(thing_id).strip()
        if not things_collection.find_one({"id": thing_id_clean}):
            orphan_thing_ids.append(thing_id_clean)
    
    if not orphan_thing_ids:
        print("\n✅ Aucun mot-clé orphelin trouvé!")
        return 0
    
    print(f"\n⚠️  Mots-clés orphelins détectés: {len(orphan_thing_ids)}")
    for thing_id in orphan_thing_ids:
        count = keyword_index_collection.count_documents({"thingId": thing_id})
        print(f"   - thingId '{thing_id}': {count} mots-clés")
    
    # Supprimer les orphelins
    print("\n🧹 Suppression des mots-clés orphelins...")
    result = keyword_index_collection.delete_many({"thingId": {"$in": orphan_thing_ids}})
    
    print(f"✅ {result.deleted_count} mots-clés orphelins supprimés!")
    
    return result.deleted_count


if __name__ == "__main__":
    try:
        cleanup_count = cleanup_orphans()
        print(f"\n🎉 Nettoyage complet! {cleanup_count} documents supprimés.")
    except Exception as e:
        print(f"\n❌ Erreur lors du nettoyage: {e}")
