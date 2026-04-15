#!/usr/bin/env python3
"""
Script d'installation et configuration du système d'index de mots clés.
Exécutez ce script UNE FOIS pour configurer tout le système.

Usage:
    python setup_keyword_index.py
"""

import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.base import keyword_index_collection, things_collection


def print_header(text: str):
    """Affiche un header de section."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def check_mongodb_connection():
    """Vérifie la connexion à MongoDB."""
    print_header("✓ Vérification de la connexion à MongoDB")
    
    try:
        # Tester la connexion
        count = things_collection.count_documents({})
        unique_count = keyword_index_collection.count_documents({})
        
        print(f"✅ MongoDB connecté")
        print(f"   • Collection 'things': {count} documents")
        print(f"   • Collection 'keyword_index': {unique_count} documents")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur de connexion MongoDB: {e}")
        print("   Vérifiez que le MongoDB est en cours d'exécution.")
        print("   URI: Vérifier dans le fichier bdd.env")
        return False


def check_existing_indexes():
    """Affiche les index existants."""
    print_header("📊 Index Existants")
    
    try:
        indexes = list(keyword_index_collection.list_indexes())
        
        if len(indexes) <= 1:  # Seulement l'index _id par défaut
            print("❌ Aucun index customisé trouvé")
            return False
        else:
            print(f"✅ {len(indexes)} index détectés:")
            for idx in indexes:
                print(f"   • {idx['name']}: {idx['key']}")
            return True
            
    except Exception as e:
        print(f"Erreur: {e}")
        return False


def create_indexes():
    """Crée tous les index nécessaires."""
    print_header("🔧 Création des Index MongoDB")
    
    try:
        from backend.create_keyword_indexes import create_keyword_indexes
        return create_keyword_indexes()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def populate_keywords():
    """Peuple la collection avec les mots clés."""
    print_header("📝 Peuplement de la Collection")
    
    try:
        from backend.populate_keywords import rebuild_keyword_index
        return rebuild_keyword_index()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def show_statistics():
    """Affiche les statistiques finales."""
    print_header("📈 Statistiques Finales")
    
    try:
        from backend.populate_keywords import get_index_statistics
        return get_index_statistics()
        
    except Exception as e:
        print(f"Erreur: {e}")
        return False


def show_next_steps():
    """Affiche les prochaines étapes."""
    print_header("🎯 Prochaines Étapes")
    
    steps = [
        ("1. Intégration dans le CRUD", [
            "• Ouvrir 'main_crud.py'",
            "• Importer: from keyword_index_integration import *",
            "• Ajouter sync_keyword_index_* dans create/update/delete",
        ]),
        ("2. Tester la Recherche", [
            "• Lancer: python main.py",
            "• Effectuer une recherche d'objet",
            "• Vérifier que les résultats sont pertinents",
        ]),
        ("3. Monitorer les Performances", [
            "• Commande: python populate_keywords.py stats",
            "• Vérifier les temps de réponse",
            "• Reconstruire si nécessaire: python populate_keywords.py rebuild",
        ]),
        ("4. Maintenance", [
            "• Chaque modification d'objet met à jour l'index",
            "• Reconstructions complètes: 1x par semaine/mois",
            "• Vérifier les logs d'erreurs",
        ]),
    ]
    
    for title, items in steps:
        print(f"\n{title}:")
        for item in items:
            print(f"  {item}")


def ask_confirmation(question: str) -> bool:
    """Demande une confirmation à l'utilisateur."""
    while True:
        choice = input(f"\n{question} (y/n): ").strip().lower()
        if choice in ['y', 'yes', 'oui', 'o']:
            return True
        elif choice in ['n', 'no', 'non']:
            return False
        else:
            print("  ❌ Veuillez entrer 'y' ou 'n'")


def main():
    """Fonction principale du setup."""
    
    print("\n")
    print("     🔍 SETUP - INDEX DE MOTS CLÉS MONGODB")
    print("     =====================================")
    print("\n     Ce script configure votre système de recherche rapide")
    print("     pour les mots clés MongoDB.\n")
    
    # Étape 1: Vérifier MongoDB
    if not check_mongodb_connection():
        print("\n❌ Impossible de continuer sans une connexion MongoDB active.")
        return False
    
    # Étape 2: Vérifier les index existants
    indexes_exist = check_existing_indexes()
    
    # Étape 3: Créer les index si nécessaire
    if not indexes_exist:
        if ask_confirmation("Créer les index MongoDB maintenant?"):
            if not create_indexes():
                print("❌ Erreur lors de la création des index")
                return False
        else:
            print("\n⚠️  Les index ne sont pas créés. Continuer quand même?")
            if not ask_confirmation("Continuer?"):
                return False
    else:
        print("✅ Les index existent déjà")
    
    # Étape 4: Peupler la collection
    existing_count = keyword_index_collection.count_documents({})
    
    if existing_count == 0 or ask_confirmation(f"Reconstruire l'index ({existing_count} documents actuels)?"):
        if not populate_keywords():
            print("❌ Erreur lors du peuplement")
            return False
    else:
        print("⏭️  Peuplement sauté")
    
    # Étape 5: Afficher les statistiques
    show_statistics()
    
    # Étape 6: Afficher les prochaines étapes
    show_next_steps()
    
    print_header("✅ SETUP TERMINÉ!")
    
    print("""
Les fichiers suivants ont été créés:
  • create_keyword_indexes.py ........... Création des index
  • populate_keywords.py ............... Peuplement de l'index
  • keyword_index_integration.py ....... Intégration dans le CRUD
  • KEYWORD_INDEX_SCHEMA.json ......... Schéma de validation
  • KEYWORD_INDEX_GUIDE.md ............ Documentation complète
  • setup_keyword_index.py ............ Ce script

Commandes utiles:
  $ python create_keyword_indexes.py analyze    # Analyser les index
  $ python populate_keywords.py stats           # Voir les statistiques
  $ python populate_keywords.py rebuild         # Reconstruire l'index
    """)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup annulé par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

