import streamlit as st
import easyocr
import pandas as pd
import re
import os
import json
import matplotlib.pyplot as plt
from datetime import datetime
from PIL import Image
import numpy as np

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Mon Budget Intelligent", layout="centered")
st.title("🛒 Mon Assistant Budget")

NOM_DICT = 'mon_dictionnaire.json'
NOM_CSV = 'mon_budget.csv'

# Liste des mots à ignorer automatiquement (Ex: Infos magasin, dates, etc.)
# NOUVEAU : On ajoute les mots parasites récurrents
MOTS_INTERDITS = ["STATION", "RUE", "AVENUE", "BOULEVARD", "TEL:", "MERCI", "REVOIR", "TOTAL", "CB", "VISA", "TICKET", "SIRET", "DATE"]

# Dictionnaire par défaut avec tes 11 catégories
DICT_INITIAL = {
    "FRUITS": ["POMME", "BANANE", "ORANGE", "PINK", "LADY"],
    "LÉGUMES": ["CAROTTE", "TOMATE", "COURGETTE", "SALADE", "CRISE"],
    "VIANDE": ["POULET", "BOEUF", "STEAK", "JAMBON"],
    "POISSON": ["SAUMON", "CABILLAUD", "THON"],
    "PRODUITS LAITIERS": ["LAIT", "YAOURT", "BEURRE", "FROMAGE", "GRANA"],
    "ÉPICERIE": ["PATES", "RIZ", "FARINE", "HUILE", "OEUF"],
    "SUCRERIES": ["CHOCOLAT", "BISCUIT", "CHOC", "COOKIE"],
    "BOISSONS": ["EAU", "JUS", "SODA", "COLA"],
    "BOISSONS ALCOOLISÉES": ["VIN", "BIERE"],
    "HYGIÈNE CORPORELLE": ["SAVON", "DENTIFRICE", "SHAMPOOING"],
    "ENTRETIEN DE LA MAISON": ["LESSIVE", "PAIC", "SOPALIN"],
    "AUTRE": []
}

# --- 2. FONCTIONS UTILES ---
def charger_memoire():
    if os.path.exists(NOM_DICT):
        with open(NOM_DICT, 'r', encoding='utf-8') as f: return json.load(f)
    return DICT_INITIAL

def sauvegarder_memoire(dico):
    with open(NOM_DICT, 'w', encoding='utf-8') as f:
        json.dump(dico, f, indent=4, ensure_ascii=False)

# Initialisation de la session pour garder les données en mémoire
if 'memoire' not in st.session_state:
    st.session_state.memoire = charger_memoire()

# --- 3. INTERFACE PAR ONGLETS ---
tab1, tab2 = st.tabs(["📸 Scanner un Ticket", "📊 Mes Statistiques"])

with tab1:
    st.header("Nouveau Scan")
    source_photo = st.radio("Source de l'image :", ("Appareil photo", "Télécharger un fichier"))
    
    if source_photo == "Appareil photo":
        image_file = st.camera_input("Prenez le ticket en photo")
    else:
        image_file = st.file_uploader("Choisissez une image...", type=['jpg', 'jpeg', 'png'])

    if image_file is not None:
        img = Image.open(image_file)
        st.image(img, caption="Ticket chargé", use_column_width=True)
        
        if st.button("Lancer l'analyse ✨"):
            with st.spinner("Lecture du ticket en cours..."):
                # Conversion image pour EasyOCR
                img_np = np.array(img)
                reader = easyocr.Reader(['fr'])
                results = reader.readtext(img_np)
                
                # Regroupement des lignes
                lignes = {}
                for (bbox, text, prob) in results:
                    if prob > 0.20:
                        y = bbox[0][1]
                        trouve = False
                        for y_l in lignes.keys():
                            if abs(y - y_l) < 15:
                                lignes[y_l].append(text)
                                trouve = True; break
                        if not trouve: lignes[y] = [text]
                
                # Traitement des données avec filtres
                new_data = []
                for y in sorted(lignes.keys()):
                    phrase = " ".join(lignes[y]).upper()
                    
                    # NOUVEAU : On ignore si un mot interdit est présent
                    if any(mot in phrase for mot in MOTS_INTERDITS):
                        continue

                    match = re.search(r'(\d+)[\s.,](\d{2})\b', phrase)
                    if match:
                        prix = float(f"{match.group(1)}.{match.group(2)}")
                        nom = phrase.replace(match.group(0), "").strip()
                        
                        # Filtre : On ignore les lignes sans texte significatif
                        if len(nom) > 3:
                            # Tentative de classification auto
                            cat_trouvee = "INCONNU"
                            for cat, mots in st.session_state.memoire.items():
                                if any(m in nom for m in mots):
                                    cat_trouvee = cat; break
                            
                            new_data.append({"Article": nom, "Prix": prix, "Cat": cat_trouvee})
                
                st.session_state.temp_items = new_data

    # --- NOUVELLE INTERFACE DE VALIDATION AVEC SUPPRESSION ---
    if 'temp_items' in st.session_state and len(st.session_state.temp_items) > 0:
        st.subheader("Validation des articles")
        st.info("Décochez les lignes qui ne sont pas des articles (ex: adresse, date...)")
        
        # On utilise st.data_editor pour une validation plus propre
        df_items = pd.DataFrame(st.session_state.temp_items)
        # On ajoute une colonne de validation
        df_items.insert(0, "Garder", True)
        
        # Affichage de l'éditeur de données
        edited_df = st.data_editor(df_items, use_container_width=True, num_rows="dynamic")
        
        if st.button("Enregistrer la sélection"):
            # Filtrage des lignes décochées
            valid_items = edited_df[edited_df["Garder"] == True]
            
            if not valid_items.empty:
                # Préparation pour la sauvegarde CSV
                final_list = []
                for _, row in valid_items.iterrows():
                    final_list.append([datetime.now().strftime("%d/%m/%Y"), row['Article'], row['Prix'], row['Cat']])
                
                # Sauvegarde CSV
                df_new = pd.DataFrame(final_list, columns=['Date', 'Article', 'Prix', 'Categorie'])
                df_new.to_csv(NOM_CSV, mode='a', index=False, header=not os.path.exists(NOM_CSV), sep=';', encoding='utf-8-sig')
                
               # Apprentissage auto discret (Version sécurisée)
                for row in final_list:
                    categorie_nom = row[3]
                    article_nom = row[1]
                    
                    # On vérifie si la catégorie existe bien dans notre dictionnaire
                    if categorie_nom in st.session_state.memoire:
                        mots = article_nom.split()
                        if mots:
                            mot = mots[0]
                            if len(mot) > 3 and mot not in st.session_state.memoire[categorie_nom]:
                                st.session_state.memoire[categorie_nom].append(mot)
                
                sauvegarder_memoire(st.session_state.memoire)
            
            # On nettoie la session
            del st.session_state.temp_items
            st.rerun()

with tab2:
    st.header("Analyse de vos dépenses")
    if os.path.exists(NOM_CSV) and os.path.getsize(NOM_CSV) > 0:
        try:
            df = pd.read_csv(NOM_CSV, sep=';', encoding='utf-8-sig')
            
            # Conversion flexible des dates
            df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
            df['Prix'] = pd.to_numeric(df['Prix'], errors='coerce')
            df = df.dropna(subset=['Date', 'Prix'])
            
            if not df.empty:
                # Résumé par catégorie
                st.subheader("Répartition par catégorie")
                recap = df.groupby('Categorie')['Prix'].sum().sort_values(ascending=False)
                st.bar_chart(recap)
                
                # Tableau complet
                st.subheader("Historique des achats")
                st.dataframe(df.sort_values('Date', ascending=False))
                
                # Bouton pour effacer
                if st.button("Effacer tout l'historique"):
                    os.remove(NOM_CSV)
                    st.rerun()
            else:
                st.info("Aucune donnée valide trouvée.")
        except Exception as e:
            st.error(f"Erreur de lecture : {e}")
            if st.button("Réinitialiser le fichier budget"):
                os.remove(NOM_CSV)
                st.rerun()
    else:
        st.info("Aucune donnée enregistrée pour le moment. Allez dans l'onglet Scanner !")
