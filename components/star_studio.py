"""
Career OS — Phase 5: STAR Studio Component
Interview simulator with STAR stories mapped to competencies.
"""

from __future__ import annotations
import streamlit as st
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict

from engine.graph_engine import GraphEngine
from engine.schemas_graph import NodeType, EdgeType


@dataclass
class STARStory:
    """Structured STAR story for interview practice."""
    id: str
    situation: str
    task: str
    action: str
    result: str
    competency_tags: List[str]
    difficulty: int
    company: str
    role: str
    metrics: List[str]


class STARStudio:
    """
    STAR Interview Simulator.
    Browse, filter, and practice STAR stories by competency.
    """
    
    def __init__(self, graph_engine: GraphEngine):
        self.engine = graph_engine
        self._load_star_stories()
    
    def _load_star_stories(self):
        """Load STAR stories from graph."""
        self.stories = []
        star_nodes = self.engine.get_nodes_by_type(NodeType.STAR_STORY)
        
        for star in star_nodes:
            # Find associated case/company/role
            company = ""
            role = ""
            
            # Traverse back to find case -> role -> company
            # STAR -> HAS_STAR_STORY <- Case -> BELONGS_TO_PROJECT -> Role -> AT_COMPANY -> Company
            # For now, get from competency tags or metadata
            
            story = STARStory(
                id=star.id,
                situation=star.situation_pt,
                task=star.task_pt,
                action=star.action_pt,
                result=star.result_pt,
                competency_tags=star.competency_tags,
                difficulty=star.difficulty,
                company="",  # Will be filled via graph traversal
                role="",
                metrics=[]
            )
            self.stories.append(story)
        
        # Enrich with company/role via graph traversal
        self._enrich_stories()
    
    def _enrich_stories(self):
        """Enrich stories with company/role context via graph traversal."""
        for story in self.stories:
            # Find case that has this STAR story
            star_edges = self.engine.get_incoming_edges(story.id)
            for edge in star_edges:
                if edge.type == EdgeType.HAS_STAR_STORY:
                    case = self.engine.get_node(edge.source_id)
                    if case and case.type == NodeType.CASE:
                        # Find role/project linked to case
                        case_edges = self.engine.get_incoming_edges(case.id)
                        for ce in case_edges:
                            if ce.type == EdgeType.BELONGS_TO_PROJECT:
                                project = self.engine.get_node(ce.source_id)
                                if project:
                                    # Find role with this achievement
                                    proj_edges = self.engine.get_outgoing_edges(project.id)
                                    for pe in proj_edges:
                                        if pe.type == EdgeType.HAS_ACHIEVEMENT:
                                            role = self.engine.get_node(pe.source_id)
                                            if role and role.type == NodeType.ROLE:
                                                story.role = role.title_pt
                                                # Find company
                                                role_edges = self.engine.get_outgoing_edges(role.id)
                                                for re in role_edges:
                                                    if re.type == EdgeType.AT_COMPANY:
                                                        comp = self.engine.get_node(re.target_id)
                                                        if comp:
                                                            story.company = comp.name
                                                break
                        break
                    break
    
    def get_competencies(self) -> List[str]:
        """Get all unique competency tags."""
        all_tags = set()
        for story in self.stories:
            all_tags.update(story.competency_tags)
        return sorted(all_tags)
    
    def get_stories_by_competency(self, competency: str) -> List[STARStory]:
        """Filter stories by competency tag."""
        return [s for s in self.stories if competency in s.competency_tags]
    
    def get_stories_by_difficulty(self, max_difficulty: int) -> List[STARStory]:
        """Filter stories by difficulty level."""
        return [s for s in self.stories if s.difficulty <= max_difficulty]
    
    def get_stories_by_company(self, company: str) -> List[STARStory]:
        """Filter stories by company."""
        return [s for s in self.stories if s.company.lower() == company.lower()]
    
    def search_stories(self, query: str) -> List[STARStory]:
        """Search stories by text in situation/task/action/result."""
        query_lower = query.lower()
        results = []
        for story in self.stories:
            if (query_lower in story.situation.lower() or
                query_lower in story.task.lower() or
                query_lower in story.action.lower() or
                query_lower in story.result.lower() or
                any(query_lower in tag.lower() for tag in story.competency_tags)):
                results.append(story)
        return results


def render_star_studio(graph_engine: GraphEngine):
    """Render STAR Studio in Streamlit."""
    studio = STARStudio(graph_engine)
    
    st.markdown("""
    <div style='background-color:#f7fafc; padding:1.5rem; border-radius:12px; border-left:5px solid #805ad5; margin-bottom:1.5rem;'>
        <h3 style='color:#1a365d; margin:0 0 0.5rem 0; display:flex; align-items:center; gap:8px;'>
            ⭐ STAR Studio — Simulador de Entrevistas
        </h3>
        <p style='color:#4a5568; margin:0; font-size:0.95rem;'>
            Navegue por suas histórias STAR organizadas por competência. Pratique respondendo perguntas comportamentais 
            usando suas conquistas reais. Cada história segue o formato <strong>Situation → Task → Action → Result</strong>.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar filters
    with st.sidebar:
        st.markdown("---")
        st.markdown("### ⭐ STAR Studio Controls")
        
        # Search
        search_query = st.text_input("🔍 Buscar histórias:", placeholder="ex: liderança, IA, ramp-up...")
        
        # Competency filter
        competencies = studio.get_competencies()
        selected_competency = st.selectbox(
            "Filtrar por competência:",
            options=["Todas"] + competencies,
            index=0
        )
        
        # Difficulty filter
        max_diff = st.slider("Dificuldade máxima (1-5):", 1, 5, 5)
        
        # Company filter
        companies = sorted(set(s.company for s in studio.stories if s.company))
        selected_company = st.selectbox(
            "Filtrar por empresa:",
            options=["Todas"] + companies,
            index=0
        )
    
    # Apply filters
    filtered_stories = studio.stories
    
    if search_query:
        filtered_stories = studio.search_stories(search_query)
    
    if selected_competency != "Todas":
        filtered_stories = [s for s in filtered_stories if selected_competency in s.competency_tags]
    
    filtered_stories = [s for s in filtered_stories if s.difficulty <= max_diff]
    
    if selected_company != "Todas":
        filtered_stories = [s for s in filtered_stories if s.company == selected_company]
    
    # Stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Histórias Disponíveis", len(filtered_stories))
    with col2:
        avg_diff = sum(s.difficulty for s in filtered_stories) / len(filtered_stories) if filtered_stories else 0
        st.metric("Dificuldade Média", f"{avg_diff:.1f}/5")
    with col3:
        unique_comps = len(set(tag for s in filtered_stories for tag in s.competency_tags))
        st.metric("Competências Cobertas", unique_comps)
    
    if not filtered_stories:
        st.info("Nenhuma história encontrada com os filtros atuais.")
        return
    
    # Display stories
    st.markdown(f"### 📚 {len(filtered_stories)} História(s) STAR Encontrada(s)")
    
    # Group by competency for organized view
    if selected_competency == "Todas":
        # Group by primary competency
        grouped = defaultdict(list)
        for story in filtered_stories:
            primary = story.competency_tags[0] if story.competency_tags else "Outros"
            grouped[primary].append(story)
        
        for comp, stories in sorted(grouped.items()):
            with st.expander(f"🏷️ {comp} ({len(stories)} histórias)", expanded=False):
                for story in stories:
                    render_star_card(story)
    else:
        # Single competency view
        for story in filtered_stories:
            render_star_card(story)


def render_star_card(story: STARStory):
    """Render a single STAR story card."""
    with st.container():
        # Header with metadata
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            company_role = f" @ {story.company}" if story.company else ""
            if story.role:
                company_role = f" — {story.role}{company_role}"
            st.markdown(f"**{story.situation[:80]}{'...' if len(story.situation) > 80 else ''}**{company_role}")
        with col2:
            st.caption(f"Dificuldade: {'⭐' * story.difficulty}")
        with col3:
            st.caption(f"Tags: {', '.join(story.competency_tags[:3])}")
        
        # STAR content in expandable sections
        tab_s, tab_t, tab_a, tab_r = st.tabs(["📍 Situation", "🎯 Task", "⚡ Action", "🏆 Result"])
        
        with tab_s:
            st.write(story.situation)
        with tab_t:
            st.write(story.task)
        with tab_a:
            st.write(story.action)
        with tab_r:
            st.write(story.result)
        
        st.markdown("---")


def render_interview_simulator(graph_engine: GraphEngine):
    """Render interview practice mode with random questions."""
    studio = STARStudio(graph_engine)
    
    st.markdown("### 🎤 Modo Simulação de Entrevista")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🎲 Nova Pergunta Aleatória", use_container_width=True, type="primary"):
            import random
            story = random.choice(studio.stories)
            st.session_state["interview_story"] = story.id
            st.session_state["interview_stage"] = "question"
            st.rerun()
    
    with col2:
        if st.button("🎯 Pergunta por Competência", use_container_width=True):
            competencies = studio.get_competencies()
            selected = st.selectbox("Escolha competência:", competencies, key="interview_comp")
            stories = studio.get_stories_by_competency(selected)
            if stories:
                import random
                story = random.choice(stories)
                st.session_state["interview_story"] = story.id
                st.session_state["interview_stage"] = "question"
                st.rerun()
    
    # Show current question
    if "interview_story" in st.session_state:
        story_id = st.session_state["interview_story"]
        story = next((s for s in studio.stories if s.id == story_id), None)
        
        if story:
            if st.session_state.get("interview_stage") == "question":
                st.markdown("---")
                st.markdown("#### ❓ Pergunta da Entrevista")
                
                # Generate question from STAR
                questions = [
                    f"Me conte sobre uma situação onde você {story.task.lower()}...",
                    f"Descreva um desafio onde você teve que {story.action.lower().split('.')[0]}...",
                    f"Como você lidou com {story.situation.lower().split('.')[0]}...",
                    f"Dê um exemplo de quando você {story.result.lower().split('.')[0]}..."
                ]
                import random
                question = random.choice(questions)
                
                st.info(f"**Pergunta:** {question}")
                st.caption(f"Competência: {', '.join(story.competency_tags)} | Empresa: {story.company or 'N/A'}")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✅ Mostrar Resposta STAR", use_container_width=True):
                        st.session_state["interview_stage"] = "answer"
                        st.rerun()
                with col_b:
                    if st.button("⏭️ Próxima Pergunta", use_container_width=True):
                        del st.session_state["interview_story"]
                        st.rerun()
            
            elif st.session_state.get("interview_stage") == "answer":
                st.markdown("---")
                st.markdown("#### ✅ Resposta Modelo (STAR)")
                
                tab_s, tab_t, tab_a, tab_r = st.tabs(["📍 S", "🎯 T", "⚡ A", "🏆 R"])
                with tab_s:
                    st.write(story.situation)
                with tab_t:
                    st.write(story.task)
                with tab_a:
                    st.write(story.action)
                with tab_r:
                    st.write(story.result)
                
                st.markdown("---")
                col_x, col_y = st.columns(2)
                with col_x:
                    if st.button("🎯 Praticar Outra", use_container_width=True):
                        st.session_state["interview_stage"] = "question"
                        st.rerun()
                with col_y:
                    if st.button("✅ Finalizar", use_container_width=True):
                        del st.session_state["interview_story"]
                        del st.session_state["interview_stage"]
                        st.rerun()


if __name__ == "__main__":
    print("STAR Studio component ready for Streamlit integration.")