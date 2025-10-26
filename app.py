# ===============================
# requirements.txt (copier-coller dans un fichier à part)
# ===============================
# streamlit UI
streamlit
pandas
python-dotenv

# ===============================
# app.py – Outil de vœux enseignants (MVP)
# ===============================
import os
import uuid
from datetime import datetime
import pandas as pd
import streamlit as st

# -------------------------------
# CONFIG GÉNÉRALE
# -------------------------------
st.set_page_config(
    page_title="Vœux enseignants – Département GC",
    page_icon="✅",
    layout="wide",
)

APP_PASSCODE = os.getenv("APP_PASSCODE", "")  # optionnel : protéger l'accès
DATA_PATH = os.getenv("DATA_PATH", "data")     # dossier des données
CATALOG_CSV = os.path.join(DATA_PATH, "matieres_all.csv")
SUBMISSIONS_CSV = os.path.join(DATA_PATH, "soumissions.csv")

# -------------------------------
# CSS léger (look moderne)
# -------------------------------
st.markdown(
    """
    <style>
    .stButton>button {border-radius: 12px; padding: 0.6rem 1rem; font-weight: 600}
    .success-box {background:#ecfdf5;border:1px solid #34d399;padding:12px;border-radius:12px}
    .warn-box {background:#fff7ed;border:1px solid #fb923c;padding:12px;border-radius:12px}
    .error-box{background:#fef2f2;border:1px solid #fca5a5;padding:12px;border-radius:12px}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------
# UTILS
# -------------------------------
@st.cache_data
def load_catalog(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # colonnes minimales attendues
    expected = {"course_code","course_title","level_code","track_code","ec_type"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans le catalogue: {missing}")
    # colonnes additionnelles tolérées: ue_code, weekly_hours, ects...
    # normalisations légères
    for c in ["level_code","track_code","ec_type"]:
        df[c] = df[c].astype(str)
    return df

@st.cache_data
def levels_order(df: pd.DataFrame):
    # ordre visuel conseillé
    order = ["L1","L2","L3","1A","2A","3A","M1","M2"]
    seen = [lvl for lvl in order if lvl in df["level_code"].unique().tolist()]
    # ajoute niveaux inattendus à la fin
    rest = [lvl for lvl in df["level_code"].unique() if lvl not in seen]
    return seen + rest


def ensure_data_paths():
    os.makedirs(DATA_PATH, exist_ok=True)
    if not os.path.exists(CATALOG_CSV):
        # squelette minimal pour tester
        demo = pd.DataFrame([
            {"course_code":"DEMO-BA-1","course_title":"Béton armé","level_code":"L3","track_code":"L-GC","ec_type":"CM"},
            {"course_code":"DEMO-RDM-1","course_title":"RDM","level_code":"L3","track_code":"L-GC","ec_type":"TD"},
        ])
        demo.to_csv(CATALOG_CSV, index=False)
    if not os.path.exists(SUBMISSIONS_CSV):
        pd.DataFrame(columns=[
            "submission_id","timestamp","teacher_uid","teacher_name","teacher_email",
            "selected_levels","min_required","total_selected","priority_valid","comment",
            "course_code","course_title","level_code","track_code","ec_type","priority"
        ]).to_csv(SUBMISSIONS_CSV, index=False)


def append_submissions(rows: list[dict]):
    df = pd.read_csv(SUBMISSIONS_CSV)
    df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
    df.to_csv(SUBMISSIONS_CSV, index=False)

# -------------------------------
# APP
# -------------------------------
ensure_data_paths()
try:
    catalog = load_catalog(CATALOG_CSV)
except Exception as e:
    st.error(f"Erreur lors du chargement du catalogue : {e}")
    st.stop()

st.title("🗂️ Outil de vœux enseignants")
st.caption("Sélectionnez vos matières (8 minimum) et classez-les par priorité.")

# Accès optionnel par passcode
if APP_PASSCODE:
    with st.expander("🔒 Accès protégé"):
        code = st.text_input("Code d'accès", type="password")
        if code != APP_PASSCODE:
            st.warning("Entrez le code d'accès correct pour continuer.")
            st.stop()

# Identité
with st.container():
    c1, c2, c3 = st.columns([1,1,1])
    teacher_uid = c1.text_input("Matricule / UID")
    teacher_name = c2.text_input("Nom & Prénom")
    teacher_email = c3.text_input("Email universitaire")

# Filtres
lvl_order = levels_order(catalog)
colA, colB, colC = st.columns([1,1,1])
levels = colA.multiselect("Niveaux à afficher", options=lvl_order, default=lvl_order)
tracks = colB.multiselect("Parcours", options=sorted(catalog["track_code"].unique()), default=sorted(catalog["track_code"].unique()))
ec_types = colC.multiselect("Types d'EC", options=sorted(catalog["ec_type"].unique()), default=sorted(catalog["ec_type"].unique()))

filtered = catalog[catalog["level_code"].isin(levels) & catalog["track_code"].isin(tracks) & catalog["ec_type"].isin(ec_types)].copy()

st.subheader("📚 Catalogue filtré")
st.dataframe(filtered[["course_code","course_title","level_code","track_code","ec_type"]], use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader("✅ Vos choix & priorités")

# Préparation du tableau éditable (sélection + priorité)
work = filtered[["course_code","course_title","level_code","track_code","ec_type"]].copy()
work["Choisir"] = False
work["Priorité"] = None

edited = st.data_editor(
    work,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "Choisir": st.column_config.CheckboxColumn("Choisir"),
        "Priorité": st.column_config.NumberColumn("Priorité", min_value=1, step=1, help="Classement 1 = priorité maximale"),
    },
)

# Préférences EDT / recommandations
txt = st.text_area("📝 Recommandations / Remarques / Préférences EDT (facultatif)", placeholder="Ex.: éviter les cours le jeudi matin; préférence pour des TD en L3; binôme souhaité…", height=120)

MIN_REQUIRED = 8

# Validation
chosen = edited[edited["Choisir"] == True].copy()
errs = []
if len(chosen) < MIN_REQUIRED:
    errs.append(f"Vous devez choisir au moins {MIN_REQUIRED} matières (actuellement {len(chosen)}).")

# contrainte : au moins 1 matière par niveau sélectionné
for lvl in levels:
    if lvl not in chosen["level_code"].unique():
        errs.append(f"Aucune matière sélectionnée pour le niveau **{lvl}**.")

# priorités uniques et complètes
if not chosen["Priorité"].notna().all():
    errs.append("Renseignez une priorité pour chaque matière sélectionnée.")
else:
    prios = chosen["Priorité"].astype(int).tolist()
    if len(set(prios)) != len(prios):
        errs.append("Les priorités doivent être **uniques** (1,2,3,…).")

submit = st.button("💾 Enregistrer mes vœux", type="primary")

if submit:
    if teacher_uid == "" or teacher_name == "" or teacher_email == "":
        st.error("Veuillez renseigner vos informations (UID, Nom, Email).")
        st.stop()
    if errs:
        st.markdown("<div class='error-box'>" + "<br>".join(errs) + "</div>", unsafe_allow_html=True)
        st.stop()

    chosen = chosen.sort_values("Priorité").copy()
    submission_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"

    rows_to_save = []
    for _, r in chosen.iterrows():
        rows_to_save.append({
            "submission_id": submission_id,
            "timestamp": timestamp,
            "teacher_uid": teacher_uid,
            "teacher_name": teacher_name,
            "teacher_email": teacher_email,
            "selected_levels": ",".join(levels),
            "min_required": MIN_REQUIRED,
            "total_selected": len(chosen),
            "priority_valid": True,
            "comment": txt,
            "course_code": r["course_code"],
            "course_title": r["course_title"],
            "level_code": r["level_code"],
            "track_code": r["track_code"],
            "ec_type": r["ec_type"],
            "priority": int(r["Priorité"]),
        })

    append_submissions(rows_to_save)

    st.markdown("<div class='success-box'>Vos vœux ont été enregistrés ✅</div>", unsafe_allow_html=True)
    # fichier récap pour téléchargement
    recap = pd.DataFrame(rows_to_save).sort_values("priority")
    st.download_button(
        "📥 Télécharger mon récapitulatif (CSV)",
        data=recap.to_csv(index=False).encode("utf-8"),
        file_name=f"mes_voeux_{teacher_uid}.csv",
        mime="text/csv",
    )

st.markdown("---")
st.caption("Version MVP – stockage CSV. On pourra brancher une base Postgres + page Admin ensuite.")

# ===============================
# data/matieres_all.csv – Exemple minimal (à remplacer par vos fichiers consolidés)
# ===============================
# course_code,course_title,ue_code,ec_type,track_code,level_code,semester_code,ects,weekly_hours,capacity_sections,prerequisites,habilitation_needed,comments
# DEMO-BA-1,Béton armé,UE-STRUCT,CM,L-GC,L3,2025-2026-S2,4,1h30,,,Oui,
# DEMO-RDM-1,RDM,UE-STRUCT,TD,L-GC,L3,2025-2026-S2,4,1h30,,,Non,
