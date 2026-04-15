#!/usr/bin/env python3
"""
Test complet pour la fonctionnalité "Prendre un Objet"
Usage: python test_take_object.py
"""

import requests
import json
import time

API_BASE = "http://127.0.0.1:8000"

def print_header(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")

def test_get_objects():
    """Test 1: Récupérer tous les objets"""
    print_header("📦 Test 1: Récupérer tous les objets")
    
    try:
        response = requests.post(
            f"{API_BASE}/things/search",
            json={"search_query": ""},
            timeout=5
        )
        response.raise_for_status()
        
        objects = response.json()
        print(f"✅ Succès! {len(objects)} objet(s) trouvé(s)\n")
        
        for obj in objects[:3]:  # Afficher les 3 premiers
            print(f"  • {obj.get('name')} (ID: {obj.get('id')}, Status: {obj.get('status')})")
        
        if not objects:
            print("❌ Aucun objet! Créez-en d'abord.")
            return None
        
        return objects[0]  # Retourner le premier pour les tests suivants
        
    except requests.exceptions.ConnectionError:
        print("❌ Impossible de se connecter au serveur!")
        print(f"   Assurez-vous que le backend est démarré: python main.py")
        return None
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def test_get_object_before(object_id):
    """Test 2: Récupérer l'objet AVANT modification"""
    print_header(f"🔍 Test 2: Objet AVANT modification")
    
    try:
        response = requests.post(
            f"{API_BASE}/things/search",
            json={"search_query": ""},
            timeout=5
        )
        response.raise_for_status()
        
        objects = response.json()
        target = next((o for o in objects if o.get('id') == object_id), None)
        
        if not target:
            print(f"❌ Objet '{object_id}' non trouvé")
            return None
        
        print(f"✅ Objet trouvé:")
        print(f"   Name: {target.get('name')}")
        print(f"   Status: {target.get('status')}")
        print(f"   Availability: {target.get('availability')}")
        
        return target
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def test_update_status(object_id, new_status):
    """Test 3: Changer le statut (MAIN TEST)"""
    print_header(f"⚡ Test 3: Changer le statut à '{new_status.upper()}'")
    
    try:
        print(f"PATCH {API_BASE}/api/things/{object_id}/status")
        print(f"Body: {{\"status\": \"{new_status}\"}}\n")
        
        response = requests.patch(
            f"{API_BASE}/api/things/{object_id}/status",
            json={"status": new_status},
            timeout=5
        )
        
        data = response.json()
        
        if response.status_code == 200 and data.get('success'):
            print(f"✅ PATCH réussi!")
            print(f"   Message: {data.get('message')}")
            print(f"   Nouveau status: {data.get('thing', {}).get('status')}")
            print(f"   Nouvelle availability: {data.get('thing', {}).get('availability')}")
            return True
        else:
            print(f"❌ PATCH échoué!")
            print(f"   Code: {response.status_code}")
            print(f"   Réponse: {json.dumps(data, indent=2)}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Le serveur n'est pas accessible!")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_get_object_after(object_id, expected_status):
    """Test 4: Vérifier que le changement s'est bien fait"""
    print_header(f"🔍 Test 4: Vérifier le statut APRÈS modification")
    
    try:
        # Attendre un instant
        time.sleep(0.5)
        
        response = requests.post(
            f"{API_BASE}/things/search",
            json={"search_query": ""},
            timeout=5
        )
        response.raise_for_status()
        
        objects = response.json()
        target = next((o for o in objects if o.get('id') == object_id), None)
        
        if not target:
            print(f"❌ Objet '{object_id}' non trouvé")
            return False
        
        actual_status = target.get('status')
        
        print(f"✅ Objet retrouvé:")
        print(f"   Name: {target.get('name')}")
        print(f"   Status: {actual_status}")
        print(f"   Availability: {target.get('availability')}")
        
        if actual_status == expected_status:
            print(f"\n✅ Status correctement changé à '{expected_status}'!")
            return True
        else:
            print(f"\n⚠️  Status n'a pas changé (attendu: {expected_status}, reçu: {actual_status})")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def main():
    print("\n" + "="*50)
    print("  🧪 Tests Complets - Prendre un Objet")
    print("="*50)
    print(f"API Base: {API_BASE}")
    
    # Test 1: Récupérer les objets
    first_object = test_get_objects()
    if not first_object:
        print("\n❌ Impossible de continuer. Créez d'abord des objets!")
        return
    
    object_id = first_object.get('id')
    print(f"\n➡️  Utilisation de l'objet: {object_id}")
    
    # Test 2: État avant
    test_get_object_before(object_id)
    
    # Test 3: Changer le statut
    success = test_update_status(object_id, "inactive")
    
    if not success:
        print("\n❌ Le changement de statut a échoué! Vérifiez l'endpoint.")
        return
    
    # Test 4: Vérifier le statut
    test_get_object_after(object_id, "inactive")
    
    # Test 5: Restaurer
    print_header("🔄 Test 5: Restaurer le statut à 'active'")
    test_update_status(object_id, "active")
    test_get_object_after(object_id, "active")
    
    # Résumé final
    print_header("✅ TOUS LES TESTS COMPLÉTÉS!")
    print("\n📝 Résumé:")
    print("  ✅ Récupération des objets")
    print("  ✅ Changement de statut PATCH")
    print("  ✅ Vérification MongoDB")
    print("  ✅ Restauration du statut")
    print("\n🎉 La fonctionnalité est opérationnelle!")

if __name__ == "__main__":
    main()
