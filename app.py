# app.py — Plateforme de vœux enseignants (Département Génie Civil)
# --------------------------------------------------------
# Dépendances : streamlit, pandas, xlsxwriter (inclus côté Streamlit Cloud)
# requirements.txt :
#   streamlit
#   pandas
#   python-dotenv
# --------------------------------------------------------

import os
from io import BytesIO
from datetime import datetime
import pandas as pd
import streamlit as st

# =======================
# CONFIG GÉNÉRALE
# =======================
st.set_page_config(
    page_title="Choix des matières - Département Génie Civil",
    page_icon="🏗️",
    layout="wide",
)

DATA_DIR = os.getenv("DATA_PATH", "data")
MATIERES_FILE = os.path.join(DATA_DIR, "matieres_all.csv")
SOUMISSIONS_FILE = os.path.join(DATA_DIR, "soumissions.csv")
ADMIN_PASS = os.getenv("ADMIN_PASS", "")  # mot de passe admin (optionnel)

os.makedirs(DATA_DIR, exist_ok=True)

# =======================
# UTILS
# =======================
@st.cache_data
def load_matieres():
    if os.path.exists(MATIERES_FILE):
        df = pd.read_csv(MATIERES_FILE).fillna("")
    else:
        df = pd.DataFrame(columns=["course_code", "course_title", "level_code", "track_code", "ec_type"])
    return df

@st.cache_data
def load_soumissions():
    if os.path.exists(SOUMISSIONS_FILE):
        return pd.read_csv(SOUMISSIONS_FILE).fillna("")
    cols = ["nom", "prenom", "email", "niveau", "parcours", "matiere", "priorite", "remarques", "date_soumission"]
    return pd.DataFrame(columns=cols)

def save_soumissions(df_new: pd.DataFrame):
    if os.path.exists(SOUMISSIONS_FILE):
        old = pd.read_csv(SOUMISSIONS_FILE)
        final = pd.concat([old, df_new], ignore_index=True)
    else:
        final = df_new
    final.to_csv(SOUMISSIONS_FILE, index=False)

def to_excel_bytes(**sheets):
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            sheet = name[:31] or "Sheet1"
            df.to_excel(writer, index=False, sheet_name=sheet)
    bio.seek(0)
    return bio

# =======================
# SIDEBAR
# =======================
matieres_df = load_matieres()
st.sidebar.header("Navigation")
mode = st.sidebar.radio("Mode", ["Enseignant", "Admin"])

# =========================================================
# MODE ENSEIGNANT (NIVEAUX ET PARCOURS OBLIGATOIRES)
# =========================================================
if mode == "Enseignant":
    st.title("🎓 Plateforme de choix des matières")
    st.caption("Département de Génie Civil")

    # --- Identité ---
    st.header("👩‍🏫 Informations personnelles")
    c1, c2 = st.columns(2)
    with c1:
        nom = st.text_input("Nom")
    with c2:
        prenom = st.text_input("Prénom")
    email = st.text_input("Adresse e-mail universitaire (facultatif)")

    st.divider()

    if matieres_df.empty:
        st.warning("⚠️ Le fichier 'matieres_all.csv' est introuvable ou vide.")
        st.stop()

    # --- Filtres d'affichage (niveaux & parcours obligatoires) ---
    st.subheader("🎚️ Filtres d'affichage")

    # Niveaux obligatoires
    ORDRE_NIVEAUX = ["Ingénieur_1", "Ingénieur_2", "Ingénieur_3", "L2", "L3", "M1", "M2"]
    presents = matieres_df["level_code"].dropna().unique().tolist()
    niveaux_obligatoires = [n for n in ORDRE_NIVEAUX if n in presents] + [n for n in presents if n not in ORDRE_NIVEAUX]

    st.markdown("**📘 Niveaux obligatoires (≥ 1 matière par niveau)**")
    st.markdown(
        " ".join(
            [f"<span style='background:#eef2ff;padding:4px 10px;border-radius:12px;margin-right:6px;'>{n}</span>"
             for n in niveaux_obligatoires]
        ),
        unsafe_allow_html=True,
    )
    niveaux_sel = niveaux_obligatoires[:]

    # Parcours obligatoires
    ORDER_TRACKS = ["Génie Civil", "Structures", "VOA", "RIB"]
    present_tracks = matieres_df[matieres_df["level_code"].isin(niveaux_sel)]["track_code"].dropna().unique().tolist()
    parcours_obligatoires = [t for t in ORDER_TRACKS if t in present_tracks] + [t for t in present_tracks if t not in ORDER_TRACKS]

    st.markdown("**🎯 Parcours obligatoires (≥ 1 matière par parcours)**")
    st.markdown(
        " ".join(
            [f"<span style='background:#fee2e2;padding:4px 10px;border-radius:12px;margin-right:6px;'>{t}</span>"
             for t in parcours_obligatoires]
        ),
        unsafe_allow_html=True,
    )
    parcours_sel = parcours_obligatoires[:]

    # Types d'EC
    ec_types_all = sorted(matieres_df["ec_type"].dropna().unique().tolist())
    ec_types_sel = st.multiselect("🧩 Types d'EC (facultatif)", options=ec_types_all, default=ec_types_all)

    # Catalogue filtré
    filtre = (
        matieres_df["level_code"].isin(niveaux_sel)
        & matieres_df["track_code"].isin(parcours_sel)
        & matieres_df["ec_type"].isin(ec_types_sel)
    )
    filtré = matieres_df.loc[filtre, ["course_code", "course_title", "level_code", "track_code", "ec_type"]].copy()

    if filtré.empty:
        st.info("Aucune matière trouvée avec ces critères.")
        st.stop()

    st.subheader(f"📚 Catalogue filtré ({len(filtré)})")
    st.dataframe(filtré, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("✅ Sélection & priorités")

    work = filtré.copy()
    work["Choisir"] = False
    work["Priorité"] = None

    edited = st.data_editor(
        work,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Choisir": st.column_config.CheckboxColumn("Choisir"),
            "Priorité": st.column_config.NumberColumn("Priorité", min_value=1, step=1),
        },
    )

    remarque = st.text_area(
        "📝 Recommandations / Remarques / Préférences EDT",
        placeholder="Ex. : éviter lundi matin, binôme souhaité...",
        height=120,
    )

    MIN_TOTAL = 8
    chosen = edited[edited["Choisir"] == True].copy()
    erreurs = []

    # Vérifications
    if len(chosen) < MIN_TOTAL:
        erreurs.append(f"Vous devez choisir au moins **{MIN_TOTAL} matières** (actuellement {len(chosen)}).")

    # Par niveau
    manquants_niv = [lvl for lvl in niveaux_sel if lvl not in chosen["level_code"].unique()]
    if manquants_niv:
        erreurs.append("Niveaux sans choix : " + ", ".join([f"**{m}**" for m in manquants_niv]) + " (min. 1 par niveau).")

    # Par parcours
    manquants_track = [t for t in parcours_sel if t not in chosen["track_code"].unique()]
    if manquants_track:
        erreurs.append("Parcours sans choix : " + ", ".join([f"**{t}**" for t in manquants_track]) + " (min. 1 par parcours).")

    # Priorités
    if not chosen.empty:
        if not chosen["Priorité"].notna().all():
            erreurs.append("Renseignez une priorité pour chaque matière sélectionnée.")
        else:
            prios = chosen["Priorité"].astype(int).tolist()
            if len(set(prios)) !=
