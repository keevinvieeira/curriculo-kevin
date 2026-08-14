"""
Career OS — Phase 5: Brain Visualizer Component
Interactive Knowledge Graph visualization with PyVis for Streamlit.
Neural path highlighting when selecting a job.
"""

from __future__ import annotations
import json
import tempfile
import os
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from engine.graph_engine import GraphEngine
from engine.schemas_graph import NodeType, EdgeType
from engine.graph_rag import GraphRAGRetriever, MatchEngine


# ============================
# COLOR SCHEMES
# ============================

NODE_COLORS = {
    NodeType.CANDIDATE: "#1a365d",          # Dark navy
    NodeType.CAREER_DNA: "#2b6cb0",         # Blue
    NodeType.COMPANY: "#2f855a",            # Green
    NodeType.ROLE: "#38a169",               # Light green
    NodeType.PROJECT: "#805ad5",            # Purple
    NodeType.BULLET_POINT: "#ecc94b",       # Yellow
    NodeType.SKILL: "#dd6b20",              # Orange
    NodeType.TOOL: "#c53030",               # Red
    NodeType.METRIC: "#319795",             # Teal
    NodeType.JOB_POSTING: "#c53030",        # Red
    NodeType.REQUIREMENT: "#e53e3e",        # Bright red
    NodeType.CASE: "#805ad5",               # Purple
    NodeType.STAR_STORY: "#d69e2e",         # Gold
}

NODE_SHAPES = {
    NodeType.CANDIDATE: "star",
    NodeType.CAREER_DNA: "diamond",
    NodeType.COMPANY: "box",
    NodeType.ROLE: "ellipse",
    NodeType.PROJECT: "triangle",
    NodeType.BULLET_POINT: "dot",
    NodeType.SKILL: "circle",
    NodeType.TOOL: "square",
    NodeType.METRIC: "triangleDown",
    NodeType.JOB_POSTING: "star",
    NodeType.REQUIREMENT: "hexagon",
    NodeType.CASE: "diamond",
    NodeType.STAR_STORY: "triangle",
}

EDGE_COLORS = {
    EdgeType.WORKED_AS: "#1a365d",
    EdgeType.AT_COMPANY: "#2f855a",
    EdgeType.HAS_ACHIEVEMENT: "#ecc94b",
    EdgeType.DEMONSTRATES: "#dd6b20",
    EdgeType.UTILIZED: "#c53030",
    EdgeType.PRODUCED_IMPACT: "#319795",
    EdgeType.SUBSET_OF: "#805ad5",
    EdgeType.RELATED_TO: "#a0aec0",
    EdgeType.REQUIRES: "#e53e3e",
    EdgeType.MAPS_TO_SKILL: "#dd6b20",
    EdgeType.MAPS_TO_TOOL: "#c53030",
    EdgeType.APPLIED_TO: "#e53e3e",
    EdgeType.HAS_CASE: "#805ad5",
    EdgeType.HAS_STAR_STORY: "#d69e2e",
    EdgeType.BELONGS_TO_PROJECT: "#805ad5",
}

EDGE_DASHES = {
    EdgeType.SUBSET_OF: [5, 5],
    EdgeType.RELATED_TO: [2, 2],
    EdgeType.MAPS_TO_SKILL: [3, 3],
    EdgeType.MAPS_TO_TOOL: [3, 3],
}

# ============================
# LEGEND (PT-BR)
# ============================

NODE_TYPE_LABELS_PT = {
    NodeType.CANDIDATE: "Você",
    NodeType.CAREER_DNA: "Career DNA",
    NodeType.COMPANY: "Empresas",
    NodeType.ROLE: "Cargos",
    NodeType.PROJECT: "Projetos",
    NodeType.BULLET_POINT: "Conquistas",
    NodeType.SKILL: "Skills",
    NodeType.TOOL: "Ferramentas",
    NodeType.METRIC: "Métricas",
    NodeType.JOB_POSTING: "Vagas",
    NodeType.REQUIREMENT: "Requisitos",
    NodeType.CASE: "Cases",
    NodeType.STAR_STORY: "STAR Stories",
}

SHAPE_GLYPHS = {
    "star": "★",
    "diamond": "◆",
    "box": "■",
    "square": "■",
    "ellipse": "●",
    "circle": "●",
    "dot": "●",
    "triangle": "▲",
    "triangleDown": "▼",
    "hexagon": "⬢",
}


# ============================
# BRAIN VISUALIZER CLASS
# ============================

class BrainVisualizer:
    """
    Interactive Knowledge Graph visualizer using PyVis.
    Supports neural path highlighting for job match analysis.
    """
    
    def __init__(
        self,
        graph_engine: GraphEngine,
        height: str = "700px",
        width: str = "100%",
        bgcolor: str = "#fafbfc",
        font_color: str = "#1a365d"
    ):
        self.engine = graph_engine
        self.height = height
        self.width = width
        self.bgcolor = bgcolor
        self.font_color = font_color
        self.net = None
        self._node_id_map = {}  # PyVis node_id -> graph node_id
    
    def build_network(
        self,
        focus_job_id: Optional[str] = None,
        highlight_paths: bool = True,
        max_nodes: int = 200,
        filter_types: Optional[List[NodeType]] = None,
        layout: str = "hierarchical"
    ) -> Network:
        """
        Build PyVis network from graph engine.
        
        Args:
            focus_job_id: If provided, highlight paths from candidate to this job
            highlight_paths: Whether to highlight neural paths
            max_nodes: Maximum nodes to render (performance)
            filter_types: Only include these node types
            layout: "hierarchical", "force", "circular"
        """
        self.net = Network(
            height=self.height,
            width=self.width,
            bgcolor=self.bgcolor,
            font_color=self.font_color,
            directed=True,
            notebook=False,
            cdn_resources="in_line"
        )
        
        # Configure physics/layout
        if layout == "hierarchical":
            self.net.set_options(self._get_hierarchical_options())
        elif layout == "force":
            self.net.set_options(self._get_force_options())
        
        # Get nodes to display
        nodes_to_show = self._select_nodes(focus_job_id, max_nodes, filter_types)
        
        # Add nodes
        self._add_nodes(nodes_to_show, focus_job_id)
        
        # Add edges
        self._add_edges(nodes_to_show, focus_job_id, highlight_paths)
        
        # Add legend
        self._add_legend()
        
        return self.net
    
    def _select_nodes(
        self,
        focus_job_id: Optional[str],
        max_nodes: int,
        filter_types: Optional[List[NodeType]]
    ) -> Set[str]:
        """Select which nodes to include in visualization."""
        selected = set()
        
        # Always include candidate
        candidates = self.engine.get_nodes_by_type(NodeType.CANDIDATE)
        if candidates:
            selected.add(candidates[0].id)
        
        # If focus job, get subgraph
        if focus_job_id:
            subgraph = self.engine.get_subgraph_for_job(focus_job_id)
            for node_data in subgraph["nodes"]:
                selected.add(node_data["id"])
        
        # If no focus job, add key nodes by type
        if not focus_job_id:
            priority_types = [
                NodeType.COMPANY, NodeType.ROLE, NodeType.SKILL,
                NodeType.TOOL, NodeType.BULLET_POINT, NodeType.CASE
            ]
            for ntype in priority_types:
                if filter_types and ntype not in filter_types:
                    continue
                nodes = self.engine.get_nodes_by_type(ntype)
                for node in nodes[:20]:  # Limit per type
                    selected.add(node.id)
                    if len(selected) >= max_nodes:
                        break
                if len(selected) >= max_nodes:
                    break
        
        return selected
    
    def _add_nodes(self, node_ids: Set[str], focus_job_id: Optional[str]):
        """Add nodes to PyVis network with styling."""
        for node_id in node_ids:
            node = self.engine.get_node(node_id)
            if not node:
                continue
            
            ntype = node.type
            color = NODE_COLORS.get(ntype, "#718096")
            shape = NODE_SHAPES.get(ntype, "dot")
            
            # Determine size based on type and importance
            size = self._get_node_size(node, ntype, focus_job_id)
            
            # Build tooltip
            title = self._build_node_tooltip(node)
            
            # Highlight focus job
            border_width = 2
            border_color = color
            if focus_job_id and node_id == focus_job_id:
                border_width = 4
                border_color = "#e53e3e"
                color = "#fff5f5"
            
            # Highlight candidate
            if node.type == NodeType.CANDIDATE:
                border_width = 3
                border_color = "#1a365d"
            
            self.net.add_node(
                node_id,
                label=self._get_node_label(node),
                title=title,
                color={
                    "background": color,
                    "border": border_color,
                    "highlight": {"background": color, "border": "#000"}
                },
                shape=shape,
                size=size,
                borderWidth=border_width,
                font={"size": 10, "color": self.font_color, "face": "Inter"},
                group=ntype.value
            )
            self._node_id_map[node_id] = node_id
    
    def _get_node_size(self, node, ntype: NodeType, focus_job_id: Optional[str]) -> int:
        """Calculate node size based on type and connectivity."""
        base_sizes = {
            NodeType.CANDIDATE: 35,
            NodeType.CAREER_DNA: 25,
            NodeType.COMPANY: 30,
            NodeType.ROLE: 25,
            NodeType.PROJECT: 20,
            NodeType.BULLET_POINT: 15,
            NodeType.SKILL: 18,
            NodeType.TOOL: 16,
            NodeType.METRIC: 14,
            NodeType.JOB_POSTING: 30,
            NodeType.REQUIREMENT: 18,
            NodeType.CASE: 22,
            NodeType.STAR_STORY: 20,
        }
        base = base_sizes.get(ntype, 15)
        
        # Boost for focus job
        if focus_job_id and hasattr(node, 'id') and node.id == focus_job_id:
            return base + 10
        
        # Boost for high-degree nodes
        degree = self.engine.graph.degree(node.id) if node.id in self.engine.graph else 0
        return min(base + degree, 50)
    
    def _get_node_label(self, node) -> str:
        """Get display label for node."""
        if node.type == NodeType.CANDIDATE:
            return node.name
        elif node.type == NodeType.COMPANY:
            return node.name
        elif node.type == NodeType.ROLE:
            return node.title_pt[:25] + ("..." if len(node.title_pt) > 25 else "")
        elif node.type == NodeType.SKILL:
            return node.name[:20] + ("..." if len(node.name) > 20 else "")
        elif node.type == NodeType.TOOL:
            return node.name[:18] + ("..." if len(node.name) > 18 else "")
        elif node.type == NodeType.BULLET_POINT:
            return "• " + node.text_pt[:30] + "..."
        elif node.type == NodeType.JOB_POSTING:
            return f"🎯 {node.title[:20]}..."
        elif node.type == NodeType.REQUIREMENT:
            return "📋 " + node.description[:30] + "..."
        elif node.type == NodeType.CASE:
            return "📁 " + node.title[:25] + "..."
        elif node.type == NodeType.STAR_STORY:
            return "⭐ " + (node.situation_pt[:25] + "..." if node.situation_pt else "STAR Story")
        elif node.type == NodeType.PROJECT:
            return node.name[:25] + ("..." if len(node.name) > 25 else "")
        elif node.type == NodeType.METRIC:
            return "📊 " + node.value_change
        elif node.type == NodeType.CAREER_DNA:
            return "🧬 Career DNA"
        else:
            return str(node.id)[:8]
    
    def _build_node_tooltip(self, node) -> str:
        """Build rich HTML tooltip for node."""
        lines = [f"<b>{node.type.value}</b>"]
        
        if node.type == NodeType.CANDIDATE:
            lines.append(f"Name: {node.name}")
            lines.append(f"Headline: {node.headline}")
            lines.append(f"Location: {node.location}")
            lines.append(f"Experience: {node.years_experience} years")
        
        elif node.type == NodeType.COMPANY:
            lines.append(f"Company: {node.name}")
            lines.append(f"Industry: {node.industry}")
        
        elif node.type == NodeType.ROLE:
            lines.append(f"Title: {node.title_pt}")
            lines.append(f"Period: {node.start_date} - {node.end_date}")
            lines.append(f"Seniority: {node.seniority.value}")
        
        elif node.type == NodeType.SKILL:
            lines.append(f"Skill: {node.name}")
            lines.append(f"Category: {node.category.value}")
            lines.append(f"Level: {node.level}/5")
        
        elif node.type == NodeType.TOOL:
            lines.append(f"Tool: {node.name}")
            lines.append(f"Type: {node.tool_type}")
            lines.append(f"Proficiency: {node.proficiency}/5")
        
        elif node.type == NodeType.BULLET_POINT:
            lines.append(f"Achievement: {node.text_pt[:200]}")
            if node.quantifiable_metric:
                lines.append(f"Metric: {node.quantifiable_metric}")
        
        elif node.type == NodeType.JOB_POSTING:
            lines.append(f"Title: {node.title}")
            lines.append(f"Company: {node.company_name}")
            lines.append(f"Location: {node.location}")
        
        elif node.type == NodeType.REQUIREMENT:
            lines.append(f"Requirement: {node.description}")
            lines.append(f"Weight: {node.importance_weight}")
            lines.append(f"Type: {node.requirement_type}")
        
        elif node.type == NodeType.CASE:
            lines.append(f"Case: {node.title}")
            lines.append(f"Company: {node.company}")
            lines.append(f"Result: {node.results_pt[:150]}")
        
        elif node.type == NodeType.METRIC:
            lines.append(f"Metric: {node.indicator}")
            lines.append(f"Change: {node.value_change}")
        
        elif node.type == NodeType.STAR_STORY:
            lines.append(f"Situation: {node.situation_pt[:150]}")
            lines.append(f"Action: {node.action_pt[:150]}")
            lines.append(f"Result: {node.result_pt[:150]}")
        
        return "<br>".join(lines)
    
    def _add_edges(self, node_ids: Set[str], focus_job_id: Optional[str], highlight_paths: bool):
        """Add edges between selected nodes."""
        edge_count = 0
        max_edges = 500  # Performance limit
        
        for node_id in node_ids:
            if edge_count >= max_edges:
                break
            
            # Outgoing edges
            for edge in self.engine.get_outgoing_edges(node_id):
                if edge.target_id in node_ids:
                    self._add_edge_to_network(edge, focus_job_id, highlight_paths)
                    edge_count += 1
                    if edge_count >= max_edges:
                        break
    
    def _add_edge_to_network(self, edge, focus_job_id: Optional[str], highlight_paths: bool):
        """Add a single edge to PyVis network."""
        etype = edge.type
        color = EDGE_COLORS.get(etype, "#a0aec0")
        dashes = EDGE_DASHES.get(etype, False)
        
        # Highlight edges on path to focus job
        width = 1.5
        if highlight_paths and focus_job_id:
            if self._is_on_focus_path(edge, focus_job_id):
                width = 3.0
                color = "#e53e3e"  # Red highlight
        
        # Special styling for SUBSET_OF (hierarchy)
        if etype == EdgeType.SUBSET_OF:
            dashes = [5, 5]
            width = 1.0
        
        # Special styling for RELATED_TO (semantic)
        if etype == EdgeType.RELATED_TO:
            dashes = [2, 2]
            width = 0.8
        
        self.net.add_edge(
            edge.source_id,
            edge.target_id,
            title=f"{etype.value}",
            color={"color": color, "highlight": "#e53e3e", "hover": "#e53e3e"},
            width=width,
            dashes=dashes,
            arrows={"to": {"enabled": True, "scaleFactor": 0.8}},
            smooth={"type": "continuous", "roundness": 0.2}
        )
    
    def _is_on_focus_path(self, edge, focus_job_id: str) -> bool:
        """Check if edge is on path from candidate to focus job."""
        # Simple heuristic: edge connects to job or its requirements
        if edge.target_id == focus_job_id or edge.source_id == focus_job_id:
            return True
        
        # Check if target is a requirement of the job
        job_reqs = self.engine.get_neighbors(focus_job_id, EdgeType.REQUIRES, "out")
        req_ids = {r.id for r in job_reqs}
        
        if edge.target_id in req_ids or edge.source_id in req_ids:
            return True
        
        # Check if connects to mapped skills/tools
        for req in job_reqs:
            mapped_skills = self.engine.get_neighbors(req.id, EdgeType.MAPS_TO_SKILL, "out")
            mapped_tools = self.engine.get_neighbors(req.id, EdgeType.MAPS_TO_TOOL, "out")
            mapped_ids = {s.id for s in mapped_skills} | {t.id for t in mapped_tools}
            
            if edge.target_id in mapped_ids or edge.source_id in mapped_ids:
                return True
        
        return False
    
    def _add_legend(self):
        """Add legend to network."""
        legend_nodes = []
        for ntype, color in NODE_COLORS.items():
            if ntype in [NodeType.CANDIDATE, NodeType.COMPANY, NodeType.ROLE, 
                        NodeType.SKILL, NodeType.TOOL, NodeType.BULLET_POINT,
                        NodeType.JOB_POSTING, NodeType.REQUIREMENT, NodeType.CASE,
                        NodeType.STAR_STORY, NodeType.CAREER_DNA]:
                legend_nodes.append({
                    "label": ntype.value,
                    "color": color,
                    "shape": NODE_SHAPES.get(ntype, "dot"),
                    "size": 15
                })
        
        # Add legend via custom HTML (PyVis doesn't have built-in legend)
        pass  # Will add via Streamlit sidebar instead
    
    def _get_hierarchical_options(self) -> str:
        return json.dumps({
            "layout": {
                "hierarchical": {
                    "enabled": True,
                    "direction": "UD",
                    "sortMethod": "directed",
                    "nodeSpacing": 150,
                    "treeSpacing": 200,
                    "levelSeparation": 150
                }
            },
            "physics": {
                "enabled": True,
                "hierarchicalRepulsion": {
                    "centralGravity": 0.0,
                    "springLength": 100,
                    "springConstant": 0.01,
                    "nodeDistance": 120,
                    "damping": 0.3
                },
                "solver": "hierarchicalRepulsion",
                "stabilization": {
                    "enabled": True,
                    "iterations": 200,
                    "updateInterval": 25,
                    "fit": True
                }
            },
            "interaction": {
                "hover": True,
                "tooltipDelay": 200,
                "hideEdgesOnDrag": True,
                "navigationButtons": True,
                "keyboard": True
            },
            "edges": {
                "smooth": {"type": "continuous", "roundness": 0.2}
            }
        })
    
    def _get_force_options(self) -> str:
        return json.dumps({
            "physics": {
                "enabled": True,
                "barnesHut": {
                    "gravitationalConstant": -2000,
                    "centralGravity": 0.3,
                    "springLength": 95,
                    "springConstant": 0.04,
                    "damping": 0.3,
                    "avoidOverlap": 0.1
                },
                "solver": "barnesHut",
                "stabilization": {
                    "enabled": True,
                    "iterations": 300,
                    "updateInterval": 25,
                    "fit": True
                }
            },
            "interaction": {
                "hover": True,
                "tooltipDelay": 200,
                "hideEdgesOnDrag": True,
                "navigationButtons": True,
                "keyboard": True
            },
            "edges": {
                "smooth": {"type": "continuous", "roundness": 0.2}
            }
        })
    
    def render_in_streamlit(self, key: str = "brain_viz") -> Optional[str]:
        """Render network in Streamlit and return selected node ID if clicked."""
        if not self.net:
            return None

        # Generate HTML in-memory (avoids pyvis write_html encoding bug on
        # Windows cp1252 with inlined resources, and skips temp files entirely)
        html_content = self.net.generate_html()

        # Inject click handler
        html_content = self._inject_click_handler(html_content)

        # Render in Streamlit
        import streamlit.components.v1 as components
        components.html(html_content, height=int(self.height.replace('px', '')), scrolling=True)

        # Return clicked node from session state
        return st.session_state.get(f"{key}_clicked_node")
    
    def _inject_click_handler(self, html: str) -> str:
        """Inject JavaScript to freeze physics after stabilization and capture node clicks."""
        script = """
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Wait for network to be ready
            setTimeout(function() {
                if (typeof network !== 'undefined') {
                    // Freeze physics once layout stabilizes (stops the spinning)
                    network.on("stabilizationIterationsDone", function() {
                        network.setOptions({physics: {enabled: false}});
                    });
                    // Safety fallback: force-freeze after 10s even if
                    // stabilization never completes
                    setTimeout(function() {
                        network.setOptions({physics: {enabled: false}});
                    }, 10000);

                    // Override PyVis click handler
                    network.on("click", function(params) {
                        if (params.nodes.length > 0) {
                            var nodeId = params.nodes[0];
                            // Send to Streamlit via parent window
                            window.parent.postMessage({
                                type: "streamlit:setComponentValue",
                                key: "brain_viz_clicked_node",
                                value: nodeId
                            }, "*");
                        }
                    });
                }
            }, 1000);
        });
        </script>
        """
        # Insert before closing body tag
        return html.replace("</body>", script + "</body>")


# ============================
# STREAMLIT WRAPPER FUNCTIONS
# ============================

def render_brain_visualizer(
    graph_engine: GraphEngine,
    focus_job_id: Optional[str] = None,
    height: str = "700px",
    layout: str = "hierarchical",
    key: str = "brain_viz"
) -> Optional[str]:
    """
    Streamlit component to render the brain visualizer.
    Returns clicked node ID.
    """
    viz = BrainVisualizer(graph_engine, height=height)
    viz.build_network(
        focus_job_id=focus_job_id,
        highlight_paths=True,
        layout=layout
    )
    return viz.render_in_streamlit(key)


def render_brain_legend(visible_types: Optional[List[NodeType]] = None):
    """Render a compact color/shape legend for the brain graph."""
    types_to_show = visible_types or list(NODE_TYPE_LABELS_PT.keys())
    items = []
    for ntype in types_to_show:
        label = NODE_TYPE_LABELS_PT.get(ntype)
        if not label:
            continue
        color = NODE_COLORS.get(ntype, "#718096")
        glyph = SHAPE_GLYPHS.get(NODE_SHAPES.get(ntype, "dot"), "●")
        items.append(
            f'<span style="display:inline-block;margin:2px 10px 2px 0;'
            f'font-size:0.85rem;color:#1a365d;white-space:nowrap;">'
            f'<span style="color:{color};font-size:1rem;">{glyph}</span>'
            f' {label}</span>'
        )
    st.markdown(
        '<div style="line-height:1.7;">' + "".join(items) + "</div>",
        unsafe_allow_html=True
    )


def render_brain_sidebar_controls(
    graph_engine: GraphEngine,
    available_jobs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Render sidebar controls for brain visualizer."""
    with st.sidebar:
        st.markdown("### 🧠 Brain Visualizer Controls")
        
        # Job selector
        job_options = ["Visão Geral (Grafo Completo)"] + [
            f"{j['title']} @ {j['company_name']}" for j in available_jobs
        ]
        selected_job = st.selectbox(
            "Focar em vaga:",
            options=job_options,
            index=0
        )
        
        focus_job_id = None
        if selected_job != "Visão Geral (Grafo Completo)":
            for job in available_jobs:
                if f"{job['title']} @ {job['company_name']}" == selected_job:
                    focus_job_id = job['job_id']
                    break
        
        # Layout selector
        layout = st.radio(
            "Layout:",
            options=["Hierárquico", "Força Direcionada"],
            index=0,
            horizontal=True
        )
        layout_map = {"Hierárquico": "hierarchical", "Força Direcionada": "force"}
        
        # Filters
        st.markdown("**Filtros de Nós:**")
        show_skills = st.checkbox("Skills", value=True)
        show_tools = st.checkbox("Tools", value=True)
        show_bullets = st.checkbox("Bullets/Conquistas", value=True)
        show_cases = st.checkbox("Cases", value=True)
        show_requirements = st.checkbox("Requisitos da Vaga", value=True)
        show_star = st.checkbox("STAR Stories", value=False)
        
        filter_types = []
        if show_skills: filter_types.append(NodeType.SKILL)
        if show_tools: filter_types.append(NodeType.TOOL)
        if show_bullets: filter_types.append(NodeType.BULLET_POINT)
        if show_cases: filter_types.append(NodeType.CASE)
        if show_requirements: filter_types.append(NodeType.REQUIREMENT)
        if show_star: filter_types.append(NodeType.STAR_STORY)
        
        # Always include these
        filter_types.extend([
            NodeType.CANDIDATE, NodeType.COMPANY, NodeType.ROLE,
            NodeType.CAREER_DNA, NodeType.JOB_POSTING
        ])
        
        return {
            "focus_job_id": focus_job_id,
            "layout": layout_map[layout],
            "filter_types": filter_types
        }


def render_node_detail_panel(graph_engine: GraphEngine, node_id: Optional[str]):
    """Render detail panel for selected node."""
    if not node_id:
        return
    
    node = graph_engine.get_node(node_id)
    if not node:
        st.warning("Nó não encontrado")
        return
    
    with st.expander(f"🔍 Detalhes: {node.type.value}", expanded=True):
        # Basic info
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if node.type == NodeType.CANDIDATE:
                st.markdown(f"**{node.name}**")
                st.caption(f"📍 {node.location} | 💼 {node.years_experience} anos exp.")
                st.caption(f"💰 {node.salary_expectation}")
            
            elif node.type == NodeType.COMPANY:
                st.markdown(f"**{node.name}**")
                st.caption(f"🏢 {node.industry}")
            
            elif node.type == NodeType.ROLE:
                st.markdown(f"**{node.title_pt}**")
                st.caption(f"📅 {node.start_date} - {node.end_date}")
                st.caption(f"🎯 {node.seniority.value}")
            
            elif node.type == NodeType.SKILL:
                st.markdown(f"**{node.name}**")
                st.caption(f"📂 {node.category.value} | Level {node.level}/5")
            
            elif node.type == NodeType.TOOL:
                st.markdown(f"**{node.name}**")
                st.caption(f"🔧 {node.tool_type} | Proficiência {node.proficiency}/5")
            
            elif node.type == NodeType.BULLET_POINT:
                st.markdown(f"**Conquista**")
                st.write(node.text_pt)
                if node.quantifiable_metric:
                    st.caption(f"📊 {node.quantifiable_metric}")
            
            elif node.type == NodeType.JOB_POSTING:
                st.markdown(f"**{node.title}** @ {node.company_name}")
                st.caption(f"📍 {node.location} | 💰 {node.salary_range}")
            
            elif node.type == NodeType.REQUIREMENT:
                st.markdown(f"**Requisito**")
                st.write(node.description)
                st.caption(f"⚖️ Peso: {node.importance_weight} | Tipo: {node.requirement_type}")
            
            elif node.type == NodeType.CASE:
                st.markdown(f"**{node.title}**")
                st.caption(f"🏢 {node.company}")
                with st.expander("Ver detalhes do Case"):
                    st.markdown(f"**Contexto:** {node.context_pt}")
                    st.markdown(f"**Desafio:** {node.challenge_pt}")
                    st.markdown(f"**Decisões:** {node.decisions_pt}")
                    st.markdown(f"**Resultados:** {node.results_pt}")
            
            elif node.type == NodeType.STAR_STORY:
                st.markdown(f"**STAR Story**")
                st.markdown(f"**Situação:** {node.situation_pt}")
                st.markdown(f"**Tarefa:** {node.task_pt}")
                st.markdown(f"**Ação:** {node.action_pt}")
                st.markdown(f"**Resultado:** {node.result_pt}")
                st.caption(f"Tags: {', '.join(node.competency_tags)}")
            
            elif node.type == NodeType.METRIC:
                st.markdown(f"**{node.indicator}**")
                st.caption(f"📈 {node.value_change}")
                st.caption(f"Contexto: {node.context_pt}")
        
        with col2:
            # Show connections
            st.markdown("**Conexões:**")
            
            # Outgoing
            out_edges = graph_engine.get_outgoing_edges(node_id)
            if out_edges:
                st.markdown("*Saídas:*")
                for e in out_edges[:10]:
                    target = graph_engine.get_node(e.target_id)
                    if target:
                        st.caption(f"→ {e.type.value}: {target.name[:30]}")
            
            # Incoming
            in_edges = graph_engine.get_incoming_edges(node_id)
            if in_edges:
                st.markdown("*Entradas:*")
                for e in in_edges[:10]:
                    source = graph_engine.get_node(e.source_id)
                    if source:
                        st.caption(f"← {e.type.value}: {source.name[:30]}")


if __name__ == "__main__":
    print("Brain Visualizer component ready for Streamlit integration.")