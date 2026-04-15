"""
Script pour créer les index MongoDB sur la collection keyword_index
pour une recherche rapide et optimisée des mots clés.
"""

from pymongo import ASCENDING, DESCENDING, TEXT
from backend.base import keyword_index_collection
import sys


def create_keyword_indexes():
    """Crée tous les index nécessaires pour la recherche rapide des mots clés."""
    
    print("🔧 Création des index pour la collection keyword_index...")
    
    try:
        # Index 1: Index simple sur le champ 'mot' (recherche par mot exact)
        # C'est le plus utilisé pour les requêtes de recherche
        print("\n1️⃣  Création de l'index sur 'mot'...")
        idx1 = keyword_index_collection.create_index(
            [("mot", ASCENDING)],
            name="idx_mot",
            background=True
        )
        print(f"   ✅ Index créé: {idx1}")
        
        # Index 2: Index composé sur 'mot' + 'thingId' pour les recherches avec filtrage par objet
        print("\n2️⃣  Création de l'index composé 'mot' + 'thingId'...")
        idx2 = keyword_index_collection.create_index(
            [("mot", ASCENDING), ("thingId", ASCENDING)],
            name="idx_mot_thingId",
            background=True
        )
        print(f"   ✅ Index créé: {idx2}")
        
        # Index 3: Index sur 'thingId' pour retrouver tous les mots clés d'un objet
        print("\n3️⃣  Création de l'index sur 'thingId'...")
        idx3 = keyword_index_collection.create_index(
            [("thingId", ASCENDING)],
            name="idx_thingId",
            background=True
        )
        print(f"   ✅ Index créé: {idx3}")
        
        # Index 4: Index sur 'poids' (weight) en ordre décroissant pour trier par pertinence
        print("\n4️⃣  Création de l'index sur 'poids' (pertinence)...")
        idx4 = keyword_index_collection.create_index(
            [("poids", DESCENDING)],
            name="idx_poids",
            background=True
        )
        print(f"   ✅ Index créé: {idx4}")
        
        # Index 5: Index texte sur 'mot' pour la recherche textuelle avec patterns
        print("\n5️⃣  Création de l'index texte sur 'mot'...")
        idx5 = keyword_index_collection.create_index(
            [("mot", TEXT)],
            name="idx_mot_text",
            background=True
        )
        print(f"   ✅ Index créé: {idx5}")
        
        # Index 6: Index composé pour les recherches avec tri par poids
        print("\n6️⃣  Création de l'index composé 'mot' + 'poids'...")
        idx6 = keyword_index_collection.create_index(
            [("mot", ASCENDING), ("poids", DESCENDING)],
            name="idx_mot_poids",
            background=True
        )
        print(f"   ✅ Index créé: {idx6}")
        
        # Afficher tous les index créés
        print("\n📊 Tous les index actuels:")
        indexes = keyword_index_collection.list_indexes()
        for idx in indexes:
            print(f"   - {idx['name']}: {idx['key']}")
        
        print("\n✨ Tous les index ont été créés avec succès!")
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur lors de la création des index: {e}")
        return False


def drop_all_indexes():
    """Supprime tous les index (sauf l'index _id par défaut)."""
    print("⚠️  Suppression de tous les index...")
    try:
        keyword_index_collection.drop_indexes()
        print("✅ Tous les index ont été supprimés")
        return True
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def analyze_current_indexes():
    """Affiche l'analyse des index existants."""
    print("\n📈 Analyse des index actuels:\n")
    
    try:
        indexes = list(keyword_index_collection.list_indexes())
        stats = keyword_index_collection.aggregate([
            {"$collStats": {"histogram": {"metadata": True}}}
        ])
        
        print(f"Nombre d'index: {len(indexes)}")
        print("\nIndex actuels:")
        for idx in indexes:
            print(f"  • {idx['name']}")
            print(f"    Clés: {idx['key']}")
        
        return True
    except Exception as e:
        print(f"Erreur lors de l'analyse: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "drop":
            drop_all_indexes()
        elif command == "analyze":
            analyze_current_indexes()
        elif command == "create":
            create_keyword_indexes()
        else:
            print(f"Commande inconnue: {command}")
            print("Commandes disponibles: create, drop, analyze")
    else:
        # Par défaut, créer les index
        create_keyword_indexes()

