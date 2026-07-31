import streamlit as st
import os
import json
import re
import datetime
from urllib.parse import urlparse

# Page configuration for a premium, clean look
st.set_page_config(
    page_title="Master Resume Adaptation Studio",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

try:
    from utils import (
        load_master_resume,
        save_master_resume,
        render_html_resume,
        render_html_cover_letter,
        convert_html_to_pdf,
        convert_resume_to_markdown,
        build_generic_adapted_resume,
        AdaptedResume,
        JobMaterials
    )
except Exception as e:
    st.error(f"⚠️ Erro ao carregar módulos (ImportError): {e}")
    st.exception(e)
    st.stop()

# Custom CSS to elevate visual design and force high-contrast white card for previews
st.markdown("""
    <style>
        .main {
            background-color: #fafbfc;
        }
        .stButton>button {
            background-color: #1a365d;
            color: white;
            border-radius: 6px;
            border: none;
            padding: 0.5rem 1rem;
            font-weight: 600;
            transition: all 0.2s ease-in-out;
        }
        .stButton>button:hover {
            background-color: #2b6cb0;
            border: none;
            box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.05);
            transform: translateY(-1px);
        }
        .stDownloadButton>button {
            background-color: #2b6cb0;
            color: white;
            border-radius: 6px;
            border: none;
            padding: 0.5rem 1.2rem;
            font-weight: 600;
            transition: all 0.2s ease-in-out;
        }
        .stDownloadButton>button:hover {
            background-color: #3182ce;
            box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.05);
            transform: translateY(-1px);
        }
        .title-container {
            margin-bottom: 2rem;
        }
        .title-text {
            color: #1a365d;
            font-weight: 800;
            margin-bottom: 0.25rem;
        }
        .subtitle-text {
            color: #4a5568;
            font-size: 1.1rem;
        }
        .card {
            background-color: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
            border: 1px solid #edf2f7;
            margin-bottom: 1.5rem;
        }
        .preview-container {
            background-color: #ffffff !important;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #cbd5e0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
    </style>
""", unsafe_allow_html=True)

# App Title
st.markdown("""
    <div class="title-container">
        <h1 class="title-text">💼 Master Resume Adaptation Studio</h1>
        <p class="subtitle-text">Exiba, customize e exporte currículos adaptados localmente em PDF e HTML.</p>
    </div>
""", unsafe_allow_html=True)

# Local files paths
LOCAL_METADATA_PATH = "metadata.json"
APPLICATIONS_FILE = "applications.json"

# Applications database helpers
def load_applications():
    if os.path.exists(APPLICATIONS_FILE):
        try:
            with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_applications(apps):
    try:
        with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(apps, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_local_metadata():
    if os.path.exists(LOCAL_METADATA_PATH):
        try:
            with open(LOCAL_METADATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"company_name": "", "role_title": ""}

metadata = load_local_metadata()

# Sidebar settings
st.sidebar.markdown("<h2 style='color:#1a365d;'>⚙️ Configurações</h2>", unsafe_allow_html=True)

# Idioma do Documento (PT / EN)
st.sidebar.markdown("<h3 style='color:#1a365d; font-size:1rem;'>🌐 Idioma do Currículo</h3>", unsafe_allow_html=True)
doc_lang = st.sidebar.radio(
    "Selecione o idioma de exibição:",
    options=["English (EN)", "Português (PT)"],
    index=0,
    help="Altera todo o conteúdo do currículo (títulos, resumo, experiências, etc.) carregando os respectivos arquivos locais."
)
doc_lang_code = "en" if "English" in doc_lang else "pt"

# Resolve paths based on selected language
resume_path = f"adapted_resume_{doc_lang_code}.json"
materials_path = f"job_materials_{doc_lang_code}.json"

# Fallback to generic names if language-specific ones don't exist
if not os.path.exists(resume_path):
    resume_path = "adapted_resume.json"
if not os.path.exists(materials_path):
    materials_path = "job_materials.json"

# Language state-change check to force reload
if "last_loaded_lang" not in st.session_state or st.session_state.last_loaded_lang != doc_lang_code:
    st.session_state.adapted_resume = None
    st.session_state.job_materials = None
    st.session_state.last_loaded_lang = doc_lang_code

# Load pre-adapted resume
if st.session_state.adapted_resume is None:
    if os.path.exists(resume_path):
        try:
            with open(resume_path, "r", encoding="utf-8") as f:
                resume_dict = json.load(f)
                st.session_state.adapted_resume = AdaptedResume(**resume_dict)
        except Exception:
            pass

# Load pre-adapted materials
if st.session_state.job_materials is None:
    if os.path.exists(materials_path):
        try:
            with open(materials_path, "r", encoding="utf-8") as f:
                materials_dict = json.load(f)
                st.session_state.job_materials = JobMaterials(**materials_dict)
        except Exception:
            pass

# Status indicators
if st.session_state.adapted_resume:
    st.sidebar.success(f"✅ Exibindo conteúdo em: {doc_lang}")
else:
    st.sidebar.warning(f"⚠️ Nenhum currículo ({doc_lang_code}) adaptado localmente.")

# Add manual refresh button
if st.sidebar.button("🔄 Recarregar Dados Locais"):
    st.session_state.adapted_resume = None
    st.session_state.job_materials = None
    metadata = load_local_metadata()
    
    if os.path.exists(resume_path):
        try:
            with open(resume_path, "r", encoding="utf-8") as f:
                st.session_state.adapted_resume = AdaptedResume(**json.load(f))
        except Exception as e:
            st.sidebar.error(f"Erro ao ler JSON: {e}")
            
    if os.path.exists(materials_path):
        try:
            with open(materials_path, "r", encoding="utf-8") as f:
                st.session_state.job_materials = JobMaterials(**json.load(f))
        except Exception as e:
            st.sidebar.error(f"Erro ao ler Materiais: {e}")
            
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("🤖 **Como Adaptar Novas Vagas:**\nEnvie o link ou texto da vaga no chat do Antigravity. O assistente gerará os currículos e materiais atualizados no seu computador, e eles aparecerão automaticamente aqui após você clicar em Recarregar!")

# Main Workspace Layout
tab_studio, tab_tracker, tab_editor = st.tabs([
    "🎯 Estúdio de Adaptação", 
    "📊 Painel de Vagas & Processos",
    "📝 Editor do Currículo Mestre"
])

# ====================
# TAB 1: ADAPTATION STUDIO
# ====================
with tab_studio:
    # Display loaded vacancy details
    company_name = metadata.get("company_name", "N/A")
    role_title = metadata.get("role_title", "N/A")
    
    st.markdown(f"""
        <div class="card" style="border-left: 5px solid #1a365d; padding: 1.2rem; background-color: #f7fafc;">
            <h3 style="color:#1a365d; margin: 0 0 10px 0; font-size:1.15rem; font-weight:800; display:flex; align-items:center; gap:8px;">
                🎯 Vaga Ativa Carregada
            </h3>
            <div style="font-size: 0.95rem; color:#2d3748; line-height: 1.6;">
                <p style="margin: 3px 0;"><strong>Empresa:</strong> {company_name}</p>
                <p style="margin: 3px 0;"><strong>Cargo / Função:</strong> {role_title}</p>
                <p style="margin: 8px 0 0 0; font-size: 0.8rem; color:#718096; font-style: italic;">
                    ✨ Este currículo e materiais foram adaptados localmente no chat do Antigravity. Use os botões abaixo para visualizar, baixar e imprimir!
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Render Fit analysis directly from metadata (if available), fallback to applications database
    fit_pct = None
    salary_exp = None
    good_points = []
    improve_points = []
    
    if "fit_score" in metadata:
        fit_pct = metadata["fit_score"]
        salary_exp = metadata.get("salary_expectation", "N/A")
        good_points = metadata.get("good_points", [])
        improve_points = metadata.get("improvement_points", [])
    else:
        # Fallback to searching database
        apps = load_applications()
        for a in apps:
            a_comp = a.get("company", "").lower().strip()
            a_role = a.get("role", "").lower().strip()
            m_comp = company_name.lower().strip()
            m_role = role_title.lower().strip()
            
            # Check if company and role match (direct or substring match)
            if (a_comp in m_comp or m_comp in a_comp) and (a_role in m_role or m_role in a_role):
                fit_pct = a.get("fit_score")
                salary_exp = a.get("salary_expectation", "N/A")
                good_points = a.get("good_points", [])
                improve_points = a.get("improvement_points", [])
                break

    if fit_pct is not None:
        color_fit = "#38a169" if fit_pct >= 85 else ("#d69e2e" if fit_pct >= 70 else "#e53e3e")
        
        # Format points as HTML lists
        good_html = "".join([f"<li style='margin-bottom:6px; font-size:0.85rem; color:#2d3748;'>✅ {pt}</li>" for pt in good_points])
        improve_html = "".join([f"<li style='margin-bottom:6px; font-size:0.85rem; color:#2d3748;'>⚠️ {pt}</li>" for pt in improve_points])
        
        st.markdown(f"""
            <div style='background-color:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:1.2rem; margin-top:12px; margin-bottom:12px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);'>
                <h4 style='color:#1a365d; margin:0 0 12px 0; font-size:1.05rem; font-weight:800; border-bottom:1px solid #edf2f7; padding-bottom:6px;'>
                    📊 Análise de Match & Fit (Esta Vaga)
                </h4>
                <div style='display: flex; gap: 20px; flex-wrap: wrap;'>
                    <div style='flex: 1; min-width: 150px; border:1px solid #e2e8f0; border-radius:8px; padding:12px; text-align:center; background-color:#f8fafc; align-self: center;'>
                        <span style='font-size:0.75rem; color:#718096; text-transform:uppercase; font-weight:600;'>Score de Match</span>
                        <h2 style='margin:5px 0; color:{color_fit}; font-size:2.2rem; font-weight:800;'>{fit_pct}%</h2>
                        <span style='font-size:0.75rem; color:#4a5568;'>Expectativa Salarial:<br><strong style='color:#1a365d;'>{salary_exp}</strong></span>
                    </div>
                    <div style='flex: 3; min-width: 280px;'>
                        <p style='margin: 0 0 6px 0; font-weight: 700; color: #2d3748; font-size:0.85rem;'>👍 Pontos Fortes (Diferenciais):</p>
                        <ul style='margin: 0 0 12px 0; padding-left: 0; list-style-type: none;'>
                            {good_html}
                        </ul>
                        <p style='margin: 0 0 6px 0; font-weight: 700; color: #2d3748; font-size:0.85rem;'>💡 Pontos de Preparação (Estudos):</p>
                        <ul style='margin: 0; padding-left: 0; list-style-type: none;'>
                            {improve_html}
                        </ul>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Display Results
    if st.session_state.adapted_resume:
        tab_html, tab_md, tab_cover, tab_form = st.tabs([
            "🖼️ Currículo Visual (HTML/PDF)", 
            "📄 Currículo Markdown", 
            "✉️ Carta de Apresentação", 
            "📝 Auxiliar de Formulários (Perguntas/Respostas)"
        ])
        
        safe_company = company_name.strip().replace(" ", "_").lower() if company_name else "vaga"
        safe_role = role_title.strip().replace(" ", "_").lower() if role_title else "cv"
        
        # Determine prefix names based on selected language
        doc_prefix = "Resume" if doc_lang_code == "en" else "Curriculo"
        letter_prefix = "Cover_Letter" if doc_lang_code == "en" else "Carta"
        
        # Render HTML version with selected document language
        with tab_html:
            html_content = render_html_resume(st.session_state.adapted_resume, target_lang=doc_lang_code)
            
            # Action controls (Download and register buttons)
            col_actions_pdf, col_actions_tracker, _ = st.columns([1, 1, 2])
            
            # PDF Download (Compiled directly in Python)
            with col_actions_pdf:
                filename_pdf = f"{doc_prefix}_Kevin_Augusto_Vieira_{safe_company}_{safe_role}_{doc_lang_code}.pdf"
                try:
                    pdf_bytes = convert_html_to_pdf(html_content)
                    st.download_button(
                        label="⬇️ Baixar Currículo PDF",
                        data=pdf_bytes,
                        file_name=filename_pdf,
                        mime="application/pdf",
                        use_container_width=True
                    )
                except Exception as pe:
                    st.error(f"Erro ao gerar PDF: {pe}")
            
            # Register in tracker board
            with col_actions_tracker:
                apps = load_applications()
                # Check if this company + role is already registered in the tracker
                already_registered = any(
                    a.get("company", "").lower() == company_name.lower() and 
                    a.get("role", "").lower() == role_title.lower()
                    for a in apps
                )
                
                if already_registered:
                    st.button("✅ Já Registrado no Painel", disabled=True, use_container_width=True)
                else:
                    if st.button("🚀 Registrar no Painel", use_container_width=True):
                        today_str = datetime.date.today().isoformat()
                        new_app = {
                            "id": str(int(datetime.datetime.now().timestamp() * 1000)),
                            "company": company_name,
                            "role": role_title,
                            "date_applied": today_str,
                            "status": "Candidatado",
                            "notes": "Adicionado automaticamente a partir do estúdio de adaptação.",
                            "url": metadata.get("url", ""),
                            "current_stage": "Candidatura",
                            "fit_score": 85,
                            "salary_expectation": "A negociar",
                            "good_points": [
                                "Perfil sênior com forte match técnico nas experiências e ferramentas solicitadas."
                            ],
                            "improvement_points": [
                                "Preparar pitch em inglês/português focado nas dores específicas da empresa."
                            ],
                            "stages": [
                                {"name": "Candidatura", "status": "Concluído", "date": today_str},
                                {"name": "Triagem (Screening)", "status": "Pendente", "date": ""},
                                {"name": "Entrevista de RH", "status": "Pendente", "date": ""},
                                {"name": "Entrevista Técnica", "status": "Pendente", "date": ""},
                                {"name": "Proposta (Offer)", "status": "Pendente", "date": ""}
                            ]
                        }
                        apps.append(new_app)
                        save_applications(apps)
                        st.success(f"Candidatura para {company_name} registrada com sucesso!")
                        st.rerun()
            
            st.info(f"💡 Exibindo currículo adaptado em **{doc_lang}**.")
            
            # Visual Preview with explicit white paper container to fix dark mode issues
            st.markdown('<div class="preview-container">', unsafe_allow_html=True)
            st.components.v1.html(html_content, height=800, scrolling=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        # Render Markdown version
        with tab_md:
            md_content = convert_resume_to_markdown(st.session_state.adapted_resume, target_lang=doc_lang_code)
            
            col_actions_md, _ = st.columns([1, 3])
            with col_actions_md:
                filename_md = f"{doc_prefix}_Kevin_Augusto_Vieira_{safe_company}_{safe_role}_{doc_lang_code}.md"
                st.download_button(
                    label="⬇️ Baixar Currículo Markdown",
                    data=md_content,
                    file_name=filename_md,
                    mime="text/plain",
                    use_container_width=True
                )
            st.code(md_content, language="markdown")
            
        # Cover Letter
        with tab_cover:
            if st.session_state.job_materials:
                letter = st.session_state.job_materials.cover_letter
                
                col_actions_cl, _ = st.columns([1, 3])
                with col_actions_cl:
                    filename_pdf_cl = f"{letter_prefix}_Kevin_Augusto_Vieira_{safe_company}_{safe_role}_{doc_lang_code}.pdf"
                    try:
                        cl_html = render_html_cover_letter(letter)
                        cl_pdf_bytes = convert_html_to_pdf(cl_html)
                        st.download_button(
                            label="⬇️ Baixar Carta de Apresentação (PDF)",
                            data=cl_pdf_bytes,
                            file_name=filename_pdf_cl,
                            mime="application/pdf",
                            use_container_width=True
                        )
                    except Exception as err_cl_pdf:
                        st.error(f"Erro ao gerar PDF da Carta de Apresentação: {err_cl_pdf}")
                    
                st.markdown('<div class="card" style="white-space: pre-wrap; font-family: sans-serif; font-size: 1rem; line-height: 1.6;">' + letter + '</div>', unsafe_allow_html=True)
            else:
                st.write("Carta de apresentação não gerada.")
            
        # Form Questions Helper
        with tab_form:
            if st.session_state.job_materials and st.session_state.job_materials.form_answers:
                st.write("Aqui estão respostas personalizadas prontas ou orientações detalhadas baseadas no seu perfil mestre para preencher perguntas complexas em portais de contratação (Gupy, Lever, etc.):")
                
                for i, item in enumerate(st.session_state.job_materials.form_answers):
                    with st.expander(f"❓ Pergunta {i+1}: {item.question}", expanded=True):
                        st.markdown(f"**Sugestão de resposta:**")
                        st.write(item.answer)
            else:
                st.write("Respostas de formulário não geradas.")

# ====================
# TAB 2: APPLICATIONS TRACKER
# ====================
with tab_tracker:
    st.subheader("📊 Painel de Controle de Candidaturas")
    st.write("Acompanhe o andamento dos seus processos seletivos e controle as etapas das entrevistas localmente.")
    
    # Load applications database
    apps = load_applications()
    
    # Dashboard metrics
    total_apps = len(apps)
    active_apps = sum(1 for a in apps if a.get("status") in ["Candidatado", "Triagem", "Entrevista", "Proposta"])
    interviews_count = sum(1 for a in apps if a.get("status") == "Entrevista")
    success_count = sum(1 for a in apps if a.get("status") == "Proposta")
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.markdown(f"""
            <div style='background-color:#ebf8ff; padding:1.2rem; border-radius:8px; border-left:5px solid #3182ce; text-align:center; box-shadow: 0 2px 4px rgba(0,0,0,0.03);'>
                <p style='margin:0; font-size:0.85rem; color:#2b6cb0; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;'>Total Enviados</p>
                <h1 style='margin:5px 0 0 0; color:#1a365d; font-size:2rem; font-weight:800;'>{total_apps}</h1>
            </div>
        """, unsafe_allow_html=True)
    with col_m2:
        st.markdown(f"""
            <div style='background-color:#e6fffa; padding:1.2rem; border-radius:8px; border-left:5px solid #319795; text-align:center; box-shadow: 0 2px 4px rgba(0,0,0,0.03);'>
                <p style='margin:0; font-size:0.85rem; color:#234e52; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;'>Processos Ativos</p>
                <h1 style='margin:5px 0 0 0; color:#1d4044; font-size:2rem; font-weight:800;'>{active_apps}</h1>
            </div>
        """, unsafe_allow_html=True)
    with col_m3:
        st.markdown(f"""
            <div style='background-color:#fefcbf; padding:1.2rem; border-radius:8px; border-left:5px solid #d69e2e; text-align:center; box-shadow: 0 2px 4px rgba(0,0,0,0.03);'>
                <p style='margin:0; font-size:0.85rem; color:#744210; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;'>Em Entrevistas</p>
                <h1 style='margin:5px 0 0 0; color:#5f370e; font-size:2rem; font-weight:800;'>{interviews_count}</h1>
            </div>
        """, unsafe_allow_html=True)
    with col_m4:
        st.markdown(f"""
            <div style='background-color:#f0fff4; padding:1.2rem; border-radius:8px; border-left:5px solid #38a169; text-align:center; box-shadow: 0 2px 4px rgba(0,0,0,0.03);'>
                <p style='margin:0; font-size:0.85rem; color:#22543d; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;'>Propostas Recebidas</p>
                <h1 style='margin:5px 0 0 0; color:#1c452f; font-size:2rem; font-weight:800;'>{success_count}</h1>
            </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
    
    # Form to add a new application manually
    with st.expander("➕ Adicionar Nova Candidatura Manuscrita"):
        with st.form("new_app_form", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                new_company = st.text_input("Empresa *", placeholder="Ex: Google")
            with col_f2:
                new_role = st.text_input("Cargo *", placeholder="Ex: Product Manager")
                
            new_url = st.text_input("URL da vaga (opcional)", placeholder="Ex: https://linkedin.com/jobs/view/...")
            new_notes = st.text_area("Observações iniciais (opcional)", placeholder="Ex: Enviado currículo.")
            
            submitted = st.form_submit_button("Salvar Candidatura 💾")
            if submitted:
                if not new_company.strip() or not new_role.strip():
                    st.error("Por favor, preencha os campos obrigatórios (Empresa e Cargo).")
                else:
                    today_str = datetime.date.today().isoformat()
                    new_app = {
                        "id": str(int(datetime.datetime.now().timestamp() * 1000)),
                        "company": new_company,
                        "role": new_role,
                        "date_applied": today_str,
                        "status": "Candidatado",
                        "notes": new_notes,
                        "url": new_url,
                        "current_stage": "Candidatura",
                        "fit_score": 80,
                        "salary_expectation": "A combinar / A negociar",
                        "good_points": [
                            "Mapeado com base no perfil sênior de 8 anos do currículo mestre."
                        ],
                        "improvement_points": [
                            "Revisar requisitos técnicos da vaga para a entrevista."
                        ],
                        "stages": [
                            {"name": "Candidatura", "status": "Concluído", "date": today_str},
                            {"name": "Triagem (Screening)", "status": "Pendente", "date": ""},
                            {"name": "Entrevista de RH", "status": "Pendente", "date": ""},
                            {"name": "Entrevista Técnica", "status": "Pendente", "date": ""},
                            {"name": "Proposta (Offer)", "status": "Pendente", "date": ""}
                        ]
                    }
                    apps.append(new_app)
                    save_applications(apps)
                    st.success(f"Candidatura para {new_company} adicionada com sucesso!")
                    st.rerun()
                    
    st.markdown("---")
    
    # Active/Inactive applications listing
    if not apps:
        st.info("Nenhuma candidatura ativa registrada no painel. Registre-a na aba Estúdio ou use o formulário acima!")
    else:
        st.subheader("📋 Suas Candidaturas Ativas (Mais Recentes Primeiro)")
        
        # Display applications in descending order (newest first)
        reversed_apps_with_orig_idx = list(reversed(list(enumerate(apps))))
        for orig_idx, app in reversed_apps_with_orig_idx:
            # Styling status badge color
            st_color = "#3182ce" # blue
            if app["status"] == "Triagem":
                st_color = "#319795" # teal
            elif app["status"] == "Entrevista":
                st_color = "#d69e2e" # gold/yellow
            elif app["status"] == "Proposta":
                st_color = "#38a169" # green
            elif app["status"] == "Rejeitado":
                st_color = "#e53e3e" # red
            elif app["status"] == "Desistente":
                st_color = "#718096" # grey
                
            badge_html = f"<span style='background-color:{st_color}; color:white; padding:3px 10px; border-radius:12px; font-size:0.75rem; font-weight:bold; margin-left:10px;'>{app['status']}</span>"
            
            role_name = app.get("role") or app.get("position") or "N/A"
            company_name_app = app.get("company", "Empresa")
            with st.expander(f"🏢 {company_name_app} — {role_name}", expanded=False):
                # Using columns to layout the information
                col_left, col_right = st.columns([2, 1])
                
                with col_left:
                    st.markdown(f"**Data de Envio:** {app['date_applied']} &nbsp;|&nbsp; **Status Geral:** {badge_html}", unsafe_allow_html=True)
                    if app.get("url"):
                        st.markdown(f"🔗 **Link da Vaga:** <a href='{app['url']}' target='_blank'>{app['url']}</a>", unsafe_allow_html=True)
                    
                    # Notes editing inside the card
                    current_notes = app.get("notes", "")
                    updated_notes = st.text_area(
                        "📝 Notas e Acompanhamento:",
                        value=current_notes,
                        height=90,
                        key=f"notes_{app['id']}"
                    )
                    if updated_notes != current_notes:
                        apps[orig_idx]["notes"] = updated_notes
                        save_applications(apps)
                        st.toast("Notas atualizadas automaticamente!")
                        
                    # Evaluation / Fit Score section (only if data exists)
                    if "fit_score" in app:
                        st.markdown("---")
                        st.markdown("<h4 style='color:#1a365d; margin-top:10px; margin-bottom:10px; font-size:1.02rem;'>📊 Análise de Match e Fit da Vaga</h4>", unsafe_allow_html=True)
                        
                        col_fit1, col_fit2 = st.columns([1, 2])
                        with col_fit1:
                            fit_pct = app["fit_score"]
                            color_fit = "#38a169" if fit_pct >= 85 else ("#d69e2e" if fit_pct >= 70 else "#e53e3e")
                            st.markdown(f"""
                                <div style='border:1px solid #e2e8f0; border-radius:8px; padding:12px; text-align:center; background-color:#f8fafc;'>
                                    <span style='font-size:0.75rem; color:#718096; text-transform:uppercase; font-weight:600;'>Score de Match</span>
                                    <h2 style='margin:5px 0; color:{color_fit}; font-size:2rem; font-weight:800;'>{fit_pct}%</h2>
                                    <span style='font-size:0.75rem; color:#4a5568;'>Expectativa Salarial:<br><strong style='color:#1a365d;'>{app.get("salary_expectation", "N/A")}</strong></span>
                                </div>
                            """, unsafe_allow_html=True)
                        
                        with col_fit2:
                            st.markdown("**Pontos Fortes (Destaques):**")
                            for pt in app.get("good_points", []):
                                st.markdown(f"✅ <span style='font-size:0.8rem; color:#2d3748;'>{pt}</span>", unsafe_allow_html=True)
                            
                            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                            st.markdown("**Pontos de Preparação / Estudos:**")
                            for pt in app.get("improvement_points", []):
                                st.markdown(f"⚠️ <span style='font-size:0.8rem; color:#2d3748;'>{pt}</span>", unsafe_allow_html=True)
                        
                with col_right:
                    # Status Select box
                    status_options = ["Candidatado", "Triagem", "Entrevista", "Proposta", "Rejeitado", "Desistente"]
                    cur_idx = status_options.index(app["status"]) if app["status"] in status_options else 0
                    new_status = st.selectbox(
                        "Alterar Etapa Geral:",
                        options=status_options,
                        index=cur_idx,
                        key=f"status_{app['id']}"
                    )
                    if new_status != app["status"]:
                        apps[orig_idx]["status"] = new_status
                        save_applications(apps)
                        st.rerun()
                        
                    # Stages Checklist (stepper helper)
                    st.markdown("🎯 **Checklist de Etapas:**")
                    stages_list = app.get("stages", [])
                    
                    for s_idx, stage in enumerate(stages_list):
                        is_completed = stage["status"] == "Concluído"
                        checked = st.checkbox(
                            stage["name"],
                            value=is_completed,
                            key=f"stage_chk_{app['id']}_{s_idx}"
                        )
                        if checked != is_completed:
                            apps[orig_idx]["stages"][s_idx]["status"] = "Concluído" if checked else "Pendente"
                            apps[orig_idx]["stages"][s_idx]["date"] = datetime.date.today().isoformat() if checked else ""
                            
                            # Auto-adjust general status depending on checked steps
                            if checked:
                                if stage["name"] == "Entrevista de RH" or stage["name"] == "Entrevista Técnica":
                                    apps[orig_idx]["status"] = "Entrevista"
                                elif stage["name"] == "Proposta (Offer)":
                                    apps[orig_idx]["status"] = "Proposta"
                                elif stage["name"] == "Triagem (Screening)" and apps[orig_idx]["status"] == "Candidatado":
                                    apps[orig_idx]["status"] = "Triagem"
                            
                            save_applications(apps)
                            st.rerun()
                            
                # Delete option
                col_del_1, col_del_2 = st.columns([4, 1])
                with col_del_2:
                    if st.button("Excluir Vaga 🗑️", key=f"del_btn_{app['id']}", use_container_width=True):
                        apps.pop(orig_idx)
                        save_applications(apps)
                        st.success("Inscrição excluída com sucesso!")
                        st.rerun()

# ====================
# TAB 3: MASTER RESUME EXPLORER / EDITOR
# ====================
with tab_editor:
    st.subheader("📝 Gerenciamento de Currículo Mestre")
    st.write("Esta área permite visualizar o seu banco de dados mestre (`master_resume.json`), baixar o currículo mestre genérico em PDF ou fazer edições diretas.")
    
    try:
        master_data_editor = load_master_resume()
        
        # Section for Downloading Generic Master Resume PDF
        st.markdown("""
            <div class="card" style="border-left: 5px solid #2b6cb0; background-color: #f7fafc; margin-bottom: 1.5rem; padding: 1.2rem;">
                <h3 style="color:#1a365d; margin: 0 0 8px 0; font-size:1.15rem; font-weight:800; display:flex; align-items:center; gap:8px;">
                    📄 Exportar Currículo Mestre Completo (PDF Genérico)
                </h3>
                <p style="color:#4a5568; font-size:0.9rem; margin-bottom: 12px; line-height: 1.5;">
                    Gere e baixe a versão em PDF do seu currículo mestre completo destacando todas as suas principais experiências profissionais com métricas de resultado, competências e certificações (em Português ou Inglês), sem estar atrelado a nenhuma vaga específica.
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        col_dl_pt, col_dl_en, _ = st.columns([1, 1, 1])
        with col_dl_pt:
            try:
                gen_pt = build_generic_adapted_resume(master_data_editor, target_lang="pt")
                html_gen_pt = render_html_resume(gen_pt, target_lang="pt")
                pdf_gen_pt = convert_html_to_pdf(html_gen_pt)
                st.download_button(
                    label="⬇️ Baixar Currículo Mestre PDF (Português)",
                    data=pdf_gen_pt,
                    file_name="Curriculo_Mestre_Kevin_Augusto_Vieira_PT.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e_pt:
                st.error(f"Erro ao gerar PDF PT: {e_pt}")
                
        with col_dl_en:
            try:
                gen_en = build_generic_adapted_resume(master_data_editor, target_lang="en")
                html_gen_en = render_html_resume(gen_en, target_lang="en")
                pdf_gen_en = convert_html_to_pdf(html_gen_en)
                st.download_button(
                    label="⬇️ Baixar Currículo Mestre PDF (English)",
                    data=pdf_gen_en,
                    file_name="Master_Resume_Kevin_Augusto_Vieira_EN.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e_en:
                st.error(f"Erro ao gerar PDF EN: {e_en}")

        st.markdown("---")

        json_str = json.dumps(master_data_editor, ensure_ascii=False, indent=2)
        
        col_ed_left, col_ed_right = st.columns([2, 1])
        
        with col_ed_left:
            st.markdown("**Modo Editor Avançado (JSON Raw)**")
            new_json_str = st.text_area(
                "Edite o JSON mestre diretamente. Cuidado para manter a estrutura e formatação válidas:",
                value=json_str,
                height=650
            )
            
            if st.button("Salvar Modificações no JSON Mestre 💾"):
                try:
                    parsed_json = json.loads(new_json_str)
                    save_master_resume(parsed_json)
                    st.success("✅ Currículo Mestre atualizado e gravado em master_resume.json com sucesso!")
                except json.JSONDecodeError as je:
                    st.error(f"❌ Erro de sintaxe no JSON: {str(je)}. Corrija a pontuação, vírgulas ou chaves e tente novamente.")
                except Exception as ex:
                    st.error(f"❌ Erro ao salvar: {str(ex)}")
                    
        with col_ed_right:
            st.markdown("**Visualização do Currículo Mestre**")
            st.info("Você pode copiar dados de novos currículos ou do seu LinkedIn e colar na estrutura JSON ao lado para enriquecer seu currículo mestre. O Gemini usará esses dados na próxima adaptação.")
            
            st.write("🔍 **Estrutura do Perfil Mestre:**")
            st.json(master_data_editor)
            
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo master_resume.json: {str(e)}")
