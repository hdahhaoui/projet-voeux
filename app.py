import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO

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
ADMIN_PASS = os.getenv("ADMIN_PASS", "")  # définis sur Render si tu veux protéger l’admin

os.makedirs(DATA_DIR, exist_ok=True)

# =======================
# UTILS
# =======================
@st.cache_data
def load_matieres():
    if os.path.exists(MATIERES_FILE):
        df = pd.read_csv(MATIERES_FILE).fillna("")
    else:
        df = pd.DataFrame(columns=["course_code","course_title","level_code","track_code","ec_type"])
    return df

@st.cache_data
def load_soumissions():
    if os.path.exists(SOUMISSIONS_FILE):
        return pd.read_csv(SOUMISSIONS_FILE).fillna("")
    # squelette si vide
    cols = ["nom","prenom","email","niveau","parcours","matiere","priorite","remarques","date_soumission"]
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
            df.to_excel(writer, index=False, sheet_name=name[:31] or "Sheet1")
    bio.seek(0)
    return bio

# =======================
# SIDEBAR
# =======================
matieres_df = load_matieres()
st.sidebar.header("Navigation")
mode = st.sidebar.radio("Mode", ["Enseignant", "Admin"])

# =======================
# MODE ENSEIGNANT (NOUVELLE VERSION MULTI-NIVEAUX)
# =======================
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
        st.warning("⚠️ `data/matieres_all.csv` est introuvable ou vide.")
        st.stop()

    # --- Filtres multi-niveaux / multi-parcours ---
    st.subheader("🎚️ Filtres d'affichage")
    niveaux_all = sorted(matieres_df["level_code"].dropna().unique().tolist())
    niveaux_sel = st.multiselect("📘 Niveaux à inclure (1 matière min. par niveau exigée)",
                                 options=niveaux_all, default=niveaux_all)

    # Parcours proposés = ceux présents dans les niveaux choisis
    parcours_all = sorted(
        matieres_df[matieres_df["level_code"].isin(niveaux_sel)]["track_code"].dropna().unique().tolist()
    )
    parcours_sel = st.multiselect("🎯 Parcours à inclure", options=parcours_all, default=parcours_all)

    # Types d'EC (optionnel)
    ec_types_all = sorted(matieres_df["ec_type"].dropna().unique().tolist())
    ec_types_sel = st.multiselect("🧩 Types d'EC (facultatif)", options=ec_types_all, default=ec_types_all)

    # Dataset filtré global (multi-niveaux)
    filtré = matieres_df[
        matieres_df["level_code"].isin(niveaux_sel)
        & matieres_df["track_code"].isin(parcours_sel)
        & matieres_df["ec_type"].isin(ec_types_sel)
    ][["course_code", "course_title", "level_code", "track_code", "ec_type"]].copy()

    if filtré.empty:
        st.info("Aucune matière pour ce filtre.")
        st.stop()

    st.subheader(f"📚 Catalogue filtré ({len(filtré)})")
    st.dataframe(filtré, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("✅ Sélection & priorités")

    # Tableau éditable avec case à cocher + priorité
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
            "Priorité": st.column_config.NumberColumn(
                "Priorité", min_value=1, step=1,
                help="Classement 1 = priorité maximale. Les priorités doivent être uniques."
            ),
        },
    )

    # Remarques EDT
    remarque = st.text_area(
        "📝 Recommandations / Remarques / Préférences EDT",
        placeholder="Ex. : éviter lundi matin ; préférence TD L3 ; binôme souhaité…",
        height=120,
    )

    MIN_TOTAL = 8  # règle globale

    # --- Validation ---
    chosen = edited[edited["Choisir"] == True].copy()
    erreurs = []

    # total ≥ 8
    if len(chosen) < MIN_TOTAL:
        erreurs.append(f"Vous devez choisir au moins **{MIN_TOTAL} matières** (actuellement {len(chosen)}).")

    # ≥ 1 par niveau sélectionné
    for lvl in niveaux_sel:
        if lvl not in chosen["level_code"].unique():
            erreurs.append(f"Aucune matière sélectionnée pour le niveau **{lvl}** (min. 1 requise).")

    # priorités renseignées et uniques
    if not chosen["Priorité"].notna().all():
        erreurs.append("Renseignez une **priorité** pour chaque matière sélectionnée.")
    else:
        prios = chosen["Priorité"].astype(int).tolist()
        if len(set(prios)) != len(prios):
            erreurs.append("Les **priorités doivent être uniques** (1, 2, 3, …).")

    # --- Enregistrement ---
    if st.button("💾 Enregistrer mes choix", type="primary"):
        if not nom.strip() or not prenom.strip():
            st.error("Veuillez renseigner votre nom et votre prénom.")
            st.stop()
        if erreurs:
            st.error("Veuillez corriger :\n- " + "\n- ".join(erreurs))
            st.stop()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lignes = []
        chosen = chosen.sort_values("Priorité")
        for _, r in chosen.iterrows():
            lignes.append({
                "nom": nom,
                "prenom": prenom,
                "email": email,
                "niveau": r["level_code"],
                "parcours": r["track_code"],
                "matiere": r["course_title"],
                "priorite": int(r["Priorité"]),
                "remarques": remarque,
                "date_soumission": now,
            })
        df_new = pd.DataFrame(lignes)
        save_soumissions(df_new)

        st.success("✅ Vos choix ont été enregistrés.")
        st.download_button(
            "📥 Télécharger mon récapitulatif (CSV)",
            data=df_new.to_csv(index=False).encode("utf-8"),
            file_name=f"choix_{nom}_{prenom}.csv",
            mime="text/csv",
        )
