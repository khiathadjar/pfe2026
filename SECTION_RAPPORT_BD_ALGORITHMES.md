# Section de rapport - Base de donnees, description des objets connectes et algorithmes

## 1. Organisation generale de la base de donnees

La persistance des donnees de notre systeme repose sur une architecture hybride combinant **Supabase** et **MongoDB**. Ce choix a ete motive par la nature heterogene des informations manipulees et par la necessite d'assurer a la fois une gestion securisee des utilisateurs et un acces efficace aux objets connectes du smart building.

D'une part, **Supabase** est utilise pour la gestion des comptes, de l'authentification et des roles. Les informations relatives aux utilisateurs sont stockees dans la table `utilisateur`, qui contient les donnees necessaires a l'identification et au controle d'acces. D'autre part, **MongoDB** est utilise pour stocker les objets connectes ainsi que les donnees directement liees a leur recherche, a leur consultation et a leur cycle d'utilisation. Cette separation des responsabilites permet de beneficier des mecanismes d'authentification de Supabase tout en exploitant la souplesse du modele documentaire pour la representation des objets et des interactions associees.

Le recours a une base documentaire pour les objets connectes se justifie par la variabilite de leurs attributs descriptifs et de leurs metadonnees de localisation. Chaque objet est represente sous la forme d'un document autonome regroupant son identifiant, son nom, son type, sa description, son etat de disponibilite et sa localisation. Cette organisation limite les operations de jointure, ameliore les temps de reponse et facilite la mise en place d'un index inverse dedie a la recherche multicritere. Elle permet egalement de conserver dans des collections distinctes l'historique d'activite des utilisateurs et les notifications systeme, sans alourdir la collection principale des objets.

Dans l'etat actuel de l'application, la persistance s'organise donc autour de **la table `utilisateur` dans Supabase** et de **quatre collections principales dans MongoDB** : `things`, `keyword_index`, `user_history` et `notifications`.

### 1.1. Table `utilisateur` (Supabase)

La table `utilisateur` assure la gestion des profils applicatifs et des roles d'acces. Dans l'implementation actuelle, les champs essentiels utilises par le systeme sont les suivants :

```json
{
  "id": "String",
  "email": "String",
  "role": "String"
}
```

Selon les besoins de presentation ou d'administration, des attributs complementaires de profil peuvent egalement etre presents, tels que `display_name`, `full_name`, `name` ou `nom`.

### 1.2. Collection `things`

La collection `things` constitue le noyau fonctionnel du systeme. Elle contient les objets connectes repertories dans le batiment intelligent.

```json
{
  "@context": "String",
  "@type": "String",
  "id": "String",
  "name": "String",
  "search_name_norm": "String",
  "type": "String",
  "description": "String",
  "status": "String",
  "availability": "String",
  "location": {
    "@type": "Place",
    "name": "String",
    "room": "String",
    "x": "Number",
    "y": "Number",
    "z": "Number"
  }
}
```

Le champ `search_name_norm` contient une version normalisee du nom de l'objet afin de faciliter la recherche textuelle. Les champs `status` et `availability` permettent de distinguer l'etat logique de l'objet et sa disponibilite operationnelle. La sous-structure `location` stocke la salle et les coordonnees necessaires au calcul de proximite spatiale.

### 1.3. Collection `keyword_index`

La collection `keyword_index` implemente un index inverse denormalise. Chaque document relie un mot-cle a un objet donne, en precisant sa provenance et son poids de pertinence.

```json
{
  "mot": "String",
  "idObjet": "Number",
  "thingId": "String",
  "poids": "Number",
  "source": "String",
  "frequence": "Number"
}
```

Le champ `mot` contient la forme normalisee du terme indexe. Le champ `thingId` reference l'objet auquel le mot est associe. Le champ `idObjet` correspond a une representation numerique derivee de l'identifiant textuel et conservee pour des besoins de reperage interne. Le couple `poids` et `frequence` permet ensuite de calculer un score lexical lors de la recherche.

### 1.4. Collection `user_history`

La collection `user_history` enregistre l'historique des activites effectuees par les utilisateurs au sein du systeme. Contrairement a une simple collection d'historique de recherche, elle couvre plusieurs types d'evenements, notamment la consultation d'informations, le debut d'emprunt, le retour d'objet et certaines actions de session.

```json
{
  "user_id": "String",
  "email": "String",
  "action": "String",
  "detail": "String",
  "status": "String",
  "date": "String",
  "created_at": "Date",
  "thing_id": "String",
  "thing_name": "String",
  "salle": "String",
  "returned": "Boolean",
  "returned_at": "Date",
  "duree_minutes": "Number"
}
```

Tous les champs ne sont pas obligatoirement presents pour chaque evenement. Leur presence depend du type d'action enregistree.

### 1.5. Collection `notifications`

La collection `notifications` centralise les messages applicatifs adresses aux utilisateurs et aux administrateurs, notamment lors des connexions, des emprunts, des retours ou des modifications d'objets.

```json
{
  "target_role": "String",
  "recipient_user_id": "String",
  "recipient_email": "String",
  "title": "String",
  "message": "String",
  "type": "String",
  "is_read": "Boolean",
  "actor_user_id": "String",
  "actor_email": "String",
  "metadata": "Object",
  "created_at": "Date",
  "updated_at": "Date"
}
```

Cette collection permet de maintenir une trace explicite des interactions systeme sans surcharger les autres collections metier.

## 2. Structure descriptive des objets connectes

Dans l'implementation actuelle, les objets connectes sont stockes dans la collection `things` sous la forme de documents MongoDB enrichis par certaines metadonnees semantiques inspirees de `Schema.org`. L'analyse des donnees effectivement presentes dans la base montre que chaque objet contient un identifiant interne, un nom, un type, une description, un statut logique, une disponibilite operationnelle ainsi qu'une localisation detaillee. Les attributs `@context` et `@type` sont egalement presents, ce qui permet d'associer l'objet a une representation semantique simple tout en restant compatible avec une formalisation plus evoluee a l'avenir.

La structure descriptive effectivement stockee dans la base peut etre resumee comme suit :

```json
{
  "@context": "String",
  "@type": "String",
  "id": "String",
  "name": "String",
  "search_name_norm": "String",
  "type": "String",
  "description": "String",
  "status": "String",
  "availability": "String",
  "location": {
    "@type": "String",
    "name": "String",
    "room": "String",
    "x": "Number",
    "y": "Number",
    "z": "Number"
  }
}
```

Dans cette structure, `name` designe le nom fonctionnel de l'objet, `type` represente sa categorie metier telle qu'elle est reellement stockee dans la base, `description` contient une description textuelle libre, `status` traduit son etat logique dans l'application, tandis que `availability` indique sa disponibilite operationnelle. La sous-structure `location` associe a chaque objet une salle de reference ainsi que des coordonnees spatiales `x`, `y` et `z`, exploitees dans les mecanismes de proximite spatiale.

Il convient donc de souligner que la base actuelle ne stocke pas encore une **Thing Description W3C Web of Things 1.1 complete**. En particulier, les sections formelles relatives aux proprietes, aux actions, aux mecanismes de securite et aux formulaires d'interaction ne sont pas materialisees telles quelles dans les documents MongoDB. Pour cette raison, la Thing Description doit etre comprise, dans le cadre du rapport, comme une **projection conceptuelle normalisee** construite a partir de la structure descriptive reelle de l'objet.

Si l'on souhaite presenter une Thing Description theorique, propre et coherente avec les donnees et les interactions du projet, la version la plus pertinente est la suivante :

```json
{
  "@context": [
    "https://www.w3.org/2022/wot/td/v1.1",
    "https://schema.org/"
  ],
  "id": "urn:dev:wot:smartbuilding:{id}",
  "title": "{titre de l'objet}",
  "description": "{description de l'objet}",
  "@type": "Product",
  "name": "{titre de l'objet}",
  "category": "{type de l'objet}",
  "forms": [
    {
      "href": "http://building.local/things/{id}",
      "htv:methodName": "GET",
      "contentType": "application/json"
    }
  ],
  "location": {
    "@type": "Place",
    "name": "{salle}",
    "room": "{salle}",
    "x": "{x}",
    "y": "{y}",
    "z": "{z}"
  },
  "securityDefinitions": {
    "nosec_sc": {
      "scheme": "nosec"
    }
  },
  "security": "nosec_sc",
  "properties": {
    "availability": {
      "type": "string",
      "enum": ["disponible", "en_utilisation", "indisponible"],
      "readOnly": true
    },
    "status": {
      "type": "string",
      "enum": ["active", "inactive"],
      "readOnly": true
    }
  },
  "actions": {
    "take": {
      "description": "Prendre l'objet pour utilisation",
      "forms": [
        {
          "href": "http://building.local/things/{id}/prendre",
          "htv:methodName": "POST"
        }
      ]
    },
    "return": {
      "description": "Retourner l'objet apres utilisation",
      "forms": [
        {
          "href": "http://building.local/things/{id}/retourner",
          "htv:methodName": "POST"
        }
      ]
    }
  }
}
```

Cette version est la plus adaptee au projet pour trois raisons. Premiere­ment, elle conserve `availability` sous forme de chaine enumeree, ce qui correspond a la realite de la base, ou les valeurs observees sont `disponible`, `en_utilisation` et `indisponible`, et non un simple booleen. Deuxiemement, elle maintient une nomenclature anglophone coherente avec l'esprit du standard WoT, notamment a travers `name`, `category`, `availability`, `take` et `return`. Enfin, elle reste compatible avec les interactions effectivement presentes dans l'application, en particulier la consultation de l'objet par `GET /things/{id}` ainsi que les operations de prise et de retour d'objet, tout en distinguant clairement cette projection conceptuelle de la structure MongoDB reellement stockee.

## 3. Algorithmes

### 3.1. Algorithme d'indexation

Avant toute recherche, le systeme construit un index inverse a partir des principaux champs textuels de chaque objet. Les memes structures sont ensuite reutilisees lors de la recherche, ce qui assure la coherence entre l'indexation et l'interrogation.

```text
Algorithme IndexationObjets
DÉBUT
  POUR CHAQUE objet DANS things FAIRE
    Supprimer de keyword_index tous les documents tels que thingId = objet.id

    ChampsIndexables ← [
      (objet.name, "TITRE", 3),
      (objet.type, "TYPE", 2),
      (objet.description, "DESCRIPTION", 1),
      (objet.location.room, "SALLE", 2)
    ]

    TableFrequences ← dictionnaire vide

    POUR CHAQUE (valeur, source, poidsBase) DANS ChampsIndexables FAIRE
      valeur_norm ← Normaliser(valeur)
      ListeMots ← ExtraireTokens(valeur_norm)

      POUR CHAQUE mot DANS ListeMots FAIRE
        SI (mot, source) existe dans TableFrequences ALORS
          TableFrequences[(mot, source)].frequence ← TableFrequences[(mot, source)].frequence + 1
        SINON
          TableFrequences[(mot, source)] ← {
            poids: poidsBase,
            frequence: 1
          }
        FIN SI
      FIN POUR
    FIN POUR

    idObjetNumerique ← ConvertirIdentifiant(objet.id)

    POUR CHAQUE (mot, source) DANS TableFrequences FAIRE
      docIndex ← {
        mot: mot,
        idObjet: idObjetNumerique,
        thingId: objet.id,
        poids: TableFrequences[(mot, source)].poids,
        source: source,
        frequence: TableFrequences[(mot, source)].frequence
      }

      Insérer docIndex dans keyword_index
    FIN POUR
  FIN POUR
FIN
```

### 3.2. Algorithme de recherche

L'algorithme de recherche traite une requete composee d'un ou de plusieurs mots-cles. La requete est d'abord nettoyee et normalisee, puis enrichie par des synonymes. La recherche combine ensuite deux mecanismes : l'exploitation de l'index inverse et l'interrogation directe de la collection `things`. La couverture des mots-cles est verifiee avant le tri, ce qui permet de privilegier les objets correspondant reellement a l'ensemble de la requete.

```text
Algorithme RechercheObjets
DÉBUT
  Lire requete_utilisateur
  Lire position_utilisateur

  requete_brute ← Nettoyer(requete_utilisateur)

  SI requete_brute = "" ALORS
    Resultats ← TousLesObjets()
    CalculerProximite(Resultats, position_utilisateur)
    Trier(Resultats, même_salle décroissant, distance croissante, nom croissant)
    Retourner Resultats
  FIN SI

  requete_norm ← Normaliser(requete_brute)
  Tokens ← ExtraireTokens(requete_norm)
  SI Tokens est vide ALORS
    Tokens ← [requete_norm]
  FIN SI

  TokensEtendus ← AjouterSynonymes(Tokens)
  StatutsCompatibles ← DétecterStatutsCompatibles(requete_norm)

  DocsIndex ← ChercherDansIndex(keyword_index, TokensEtendus)
  ScoreIndex ← dictionnaire vide

  POUR CHAQUE doc DANS DocsIndex FAIRE
    SI doc.thingId n'existe pas dans ScoreIndex ALORS
      ScoreIndex[doc.thingId] ← 0
    FIN SI
    ScoreIndex[doc.thingId] ← ScoreIndex[doc.thingId] + (doc.poids × max(1, doc.frequence))
  FIN POUR

  Candidats ← ChercherDansThings(
    TokensEtendus,
    champs = [search_name_norm, name, type, description, availability, location.room, status]
  )

  Resultats ← liste vide

  POUR CHAQUE objet DANS Candidats FAIRE
    objet.nbMotsCorrespondants ← CompterTokensPrésents(objet, Tokens, TokensEtendus)
    objet.scoreFlou ← SimilaritéPartielle(requete_norm, TextePrincipal(objet))
    objet.scoreIndex ← ValeurOuZero(ScoreIndex[objet.id])
    objet.statutCompatible ← StatutCorrespond(objet, StatutsCompatibles)

    SI objet.nbMotsCorrespondants = Nombre(Tokens)
       OU objet.scoreFlou ≥ seuil_flou
       OU objet.scoreIndex > 0
       OU objet.statutCompatible = VRAI ALORS
      objet.scoreRecherche ← objet.scoreFlou + objet.scoreIndex
      Ajouter objet à Resultats
    FIN SI
  FIN POUR

  SI Resultats est vide ALORS
    Resultats ← RechercheFloueGlobale(requete_norm, seuil_secours)
  FIN SI

  CalculerProximite(Resultats, position_utilisateur)
  ResultatsTries ← ClasserResultats(Resultats)

  Retourner ResultatsTries
FIN
```

### 3.3. Algorithme de classement des resultats

Le classement final reste volontairement simple afin de refleter le comportement effectif de l'application. L'accessibilite physique de l'objet est privilegiee avant la seule pertinence textuelle.

```text
Algorithme ClassementResultats
DÉBUT
  POUR CHAQUE objet DANS Resultats FAIRE
    SI objet.same_room = VRAI ALORS
      objet.prioriteSalle ← 0
    SINON
      objet.prioriteSalle ← 1
    FIN SI

    objet.prioriteDistance ← objet.distance
    objet.prioriteScore ← -objet.scoreRecherche
    objet.prioriteNom ← Normaliser(objet.name)
  FIN POUR

  ResultatsTries ← Trier(
    Resultats,
    par (prioriteSalle, prioriteDistance, prioriteScore, prioriteNom)
  )

  Retourner ResultatsTries
FIN
```

