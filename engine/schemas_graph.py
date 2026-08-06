"""
Career OS — Graph Schemas (Pydantic Models)
Nodes, Edges, and Ontology models for the Knowledge Graph.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from uuid import uuid4


# ============================
# ENUMS & CONSTANTS
# ============================

class NodeType(str, Enum):
    CANDIDATE = "Candidate"
    COMPANY = "Company"
    ROLE = "Role"
    PROJECT = "Project"
    BULLET_POINT = "BulletPoint"
    SKILL = "Skill"
    TOOL = "Tool"
    METRIC = "Metric"
    CAREER_DNA = "CareerDNA"
    JOB_POSTING = "JobPosting"
    REQUIREMENT = "Requirement"
    CASE = "Case"
    STAR_STORY = "STARStory"


class EdgeType(str, Enum):
    WORKED_AS = "WORKED_AS"
    AT_COMPANY = "AT_COMPANY"
    HAS_ACHIEVEMENT = "HAS_ACHIEVEMENT"
    DEMONSTRATES = "DEMONSTRATES"
    UTILIZED = "UTILIZED"
    PRODUCED_IMPACT = "PRODUCED_IMPACT"
    SUBSET_OF = "SUBSET_OF"
    RELATED_TO = "RELATED_TO"
    REQUIRES = "REQUIRES"
    MAPS_TO_SKILL = "MAPS_TO_SKILL"
    MAPS_TO_TOOL = "MAPS_TO_TOOL"
    APPLIED_TO = "APPLIED_TO"
    HAS_CASE = "HAS_CASE"
    HAS_STAR_STORY = "HAS_STAR_STORY"
    BELONGS_TO_PROJECT = "BELONGS_TO_PROJECT"


class SkillCategory(str, Enum):
    AI_ML = "AI & Machine Learning"
    PRODUCT_DISCOVERY = "Product Discovery"
    GROWTH = "Growth & Marketing"
    PRODUCT_OPS = "Product Operations"
    PMM = "Product Marketing"
    LEADERSHIP = "Leadership & Management"
    TECHNICAL = "Technical & Engineering"
    DATA_ANALYTICS = "Data & Analytics"
    AUTOMATION = "Automation & No-Code"
    STRATEGY = "Strategy & GTM"
    SALES_OPS = "Sales & Operations"


class SeniorityLevel(str, Enum):
    JUNIOR = "Junior"
    MID = "Mid"
    SENIOR = "Senior"
    LEAD = "Lead"
    PRINCIPAL = "Principal"
    DIRECTOR = "Director"
    VP = "VP"
    C_LEVEL = "C-Level"


class RequirementType(str, Enum):
    MUST_HAVE = "Must Have"
    NICE_TO_HAVE = "Nice to Have"
    PREFERRED = "Preferred"


# ============================
# BASE MODELS
# ============================

class BaseNode(BaseModel):
    """Base node with common fields."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: NodeType
    user_id: str = "kevin_augusto"  # Multi-profile support
    profile_id: str = "default"
    created_at: str = Field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())


class BaseEdge(BaseModel):
    """Base edge with common fields."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EdgeType
    source_id: str
    target_id: str
    weight: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = "kevin_augusto"
    profile_id: str = "default"
    created_at: str = Field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())


# ============================
# NODE MODELS
# ============================

class CandidateNode(BaseNode):
    type: Literal[NodeType.CANDIDATE] = NodeType.CANDIDATE
    name: str
    email: str
    phone: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""
    location: str = ""
    salary_expectation: str = ""
    headline: str = ""
    years_experience: int = 0


class CompanyNode(BaseNode):
    type: Literal[NodeType.COMPANY] = NodeType.COMPANY
    name: str
    industry: str = ""
    size: str = ""
    location: str = ""
    description: str = ""
    website: str = ""


class RoleNode(BaseNode):
    type: Literal[NodeType.ROLE] = NodeType.ROLE
    title_pt: str
    title_en: str
    start_date: str
    end_date: str = "Present"
    seniority: SeniorityLevel = SeniorityLevel.SENIOR
    description_pt: str = ""
    description_en: str = ""
    is_current: bool = False


class ProjectNode(BaseNode):
    type: Literal[NodeType.PROJECT] = NodeType.PROJECT
    name: str
    description_pt: str = ""
    description_en: str = ""
    objective_pt: str = ""
    objective_en: str = ""
    start_date: str = ""
    end_date: str = ""
    status: str = "completed"


class BulletPointNode(BaseNode):
    type: Literal[NodeType.BULLET_POINT] = NodeType.BULLET_POINT
    text_pt: str
    text_en: str
    quantifiable_metric: str = ""
    impact_value: float = 0.0
    context_pt: str = ""
    context_en: str = ""
    trade_offs_pt: str = ""
    trade_offs_en: str = ""
    star_situation_pt: str = ""
    star_situation_en: str = ""
    star_task_pt: str = ""
    star_task_en: str = ""
    star_action_pt: str = ""
    star_action_en: str = ""
    star_result_pt: str = ""
    star_result_en: str = ""


class SkillNode(BaseNode):
    type: Literal[NodeType.SKILL] = NodeType.SKILL
    name: str
    category: SkillCategory
    level: int = 3  # 1-5
    description_pt: str = ""
    description_en: str = ""
    years_experience: float = 0.0


class ToolNode(BaseNode):
    type: Literal[NodeType.TOOL] = NodeType.TOOL
    name: str
    vendor: str = ""
    tool_type: str = ""  # Orchestrator, CRM, AI, Analytics, etc.
    proficiency: int = 3  # 1-5
    description_pt: str = ""
    description_en: str = ""


class MetricNode(BaseNode):
    type: Literal[NodeType.METRIC] = NodeType.METRIC
    indicator: str
    value_change: str  # e.g., "+150%", "-50%", "505 leads"
    unit: str = ""
    baseline: str = ""
    context_pt: str = ""
    context_en: str = ""


class CareerDNANode(BaseNode):
    type: Literal[NodeType.CAREER_DNA] = NodeType.CAREER_DNA
    values: List[str] = Field(default_factory=list)
    decision_style: str = ""
    leadership_style: str = ""
    favorite_problems: List[str] = Field(default_factory=list)
    work_philosophy_pt: str = ""
    work_philosophy_en: str = ""


class JobPostingNode(BaseNode):
    type: Literal[NodeType.JOB_POSTING] = NodeType.JOB_POSTING
    company_name: str
    title: str
    url: str = ""
    raw_text: str = ""
    location: str = ""
    salary_range: str = ""
    employment_type: str = ""
    seniority: SeniorityLevel = SeniorityLevel.SENIOR
    status: str = "active"


class RequirementNode(BaseNode):
    type: Literal[NodeType.REQUIREMENT] = NodeType.REQUIREMENT
    description: str
    importance_weight: float = 1.0
    requirement_type: RequirementType = RequirementType.MUST_HAVE
    category: str = ""


class CaseNode(BaseNode):
    type: Literal[NodeType.CASE] = NodeType.CASE
    title: str
    company: str
    context_pt: str = ""
    context_en: str = ""
    challenge_pt: str = ""
    challenge_en: str = ""
    problem_pt: str = ""
    problem_en: str = ""
    hypotheses_pt: str = ""
    hypotheses_en: str = ""
    decisions_pt: str = ""
    decisions_en: str = ""
    tradeoffs_pt: str = ""
    tradeoffs_en: str = ""
    results_pt: str = ""
    results_en: str = ""
    metrics: List[str] = Field(default_factory=list)


class STARStoryNode(BaseNode):
    type: Literal[NodeType.STAR_STORY] = NodeType.STAR_STORY
    situation_pt: str = ""
    situation_en: str = ""
    task_pt: str = ""
    task_en: str = ""
    action_pt: str = ""
    action_en: str = ""
    result_pt: str = ""
    result_en: str = ""
    competency_tags: List[str] = Field(default_factory=list)
    difficulty: int = 3  # 1-5


# ============================
# EDGE MODELS
# ============================

class WorkedAsEdge(BaseEdge):
    type: Literal[EdgeType.WORKED_AS] = EdgeType.WORKED_AS


class AtCompanyEdge(BaseEdge):
    type: Literal[EdgeType.AT_COMPANY] = EdgeType.AT_COMPANY


class HasAchievementEdge(BaseEdge):
    type: Literal[EdgeType.HAS_ACHIEVEMENT] = EdgeType.HAS_ACHIEVEMENT


class DemonstratesEdge(BaseEdge):
    type: Literal[EdgeType.DEMONSTRATES] = EdgeType.DEMONSTRATES
    confidence: float = 1.0


class UtilizedEdge(BaseEdge):
    type: Literal[EdgeType.UTILIZED] = EdgeType.UTILIZED
    proficiency: int = 3


class ProducedImpactEdge(BaseEdge):
    type: Literal[EdgeType.PRODUCED_IMPACT] = EdgeType.PRODUCED_IMPACT


class SubsetOfEdge(BaseEdge):
    type: Literal[EdgeType.SUBSET_OF] = EdgeType.SUBSET_OF


class RelatedToEdge(BaseEdge):
    type: Literal[EdgeType.RELATED_TO] = EdgeType.RELATED_TO
    strength: float = 0.5


class RequiresEdge(BaseEdge):
    type: Literal[EdgeType.REQUIRES] = EdgeType.REQUIRES
    importance_weight: float = 1.0


class MapsToSkillEdge(BaseEdge):
    type: Literal[EdgeType.MAPS_TO_SKILL] = EdgeType.MAPS_TO_SKILL


class MapsToToolEdge(BaseEdge):
    type: Literal[EdgeType.MAPS_TO_TOOL] = EdgeType.MAPS_TO_TOOL


class AppliedToEdge(BaseEdge):
    type: Literal[EdgeType.APPLIED_TO] = EdgeType.APPLIED_TO
    status: str = "applied"
    match_score: float = 0.0


class HasCaseEdge(BaseEdge):
    type: Literal[EdgeType.HAS_CASE] = EdgeType.HAS_CASE


class HasStarStoryEdge(BaseEdge):
    type: Literal[EdgeType.HAS_STAR_STORY] = EdgeType.HAS_STAR_STORY


class BelongsToProjectEdge(BaseEdge):
    type: Literal[EdgeType.BELONGS_TO_PROJECT] = EdgeType.BELONGS_TO_PROJECT


# ============================
# UNION TYPES & REGISTRY
# ============================

NodeModel = (
    CandidateNode | CompanyNode | RoleNode | ProjectNode | BulletPointNode |
    SkillNode | ToolNode | MetricNode | CareerDNANode | JobPostingNode |
    RequirementNode | CaseNode | STARStoryNode
)

EdgeModel = (
    WorkedAsEdge | AtCompanyEdge | HasAchievementEdge | DemonstratesEdge |
    UtilizedEdge | ProducedImpactEdge | SubsetOfEdge | RelatedToEdge |
    RequiresEdge | MapsToSkillEdge | MapsToToolEdge | AppliedToEdge |
    HasCaseEdge | HasStarStoryEdge | BelongsToProjectEdge
)

NODE_REGISTRY: Dict[NodeType, type[BaseNode]] = {
    NodeType.CANDIDATE: CandidateNode,
    NodeType.COMPANY: CompanyNode,
    NodeType.ROLE: RoleNode,
    NodeType.PROJECT: ProjectNode,
    NodeType.BULLET_POINT: BulletPointNode,
    NodeType.SKILL: SkillNode,
    NodeType.TOOL: ToolNode,
    NodeType.METRIC: MetricNode,
    NodeType.CAREER_DNA: CareerDNANode,
    NodeType.JOB_POSTING: JobPostingNode,
    NodeType.REQUIREMENT: RequirementNode,
    NodeType.CASE: CaseNode,
    NodeType.STAR_STORY: STARStoryNode,
}

EDGE_REGISTRY: Dict[EdgeType, type[BaseEdge]] = {
    EdgeType.WORKED_AS: WorkedAsEdge,
    EdgeType.AT_COMPANY: AtCompanyEdge,
    EdgeType.HAS_ACHIEVEMENT: HasAchievementEdge,
    EdgeType.DEMONSTRATES: DemonstratesEdge,
    EdgeType.UTILIZED: UtilizedEdge,
    EdgeType.PRODUCED_IMPACT: ProducedImpactEdge,
    EdgeType.SUBSET_OF: SubsetOfEdge,
    EdgeType.RELATED_TO: RelatedToEdge,
    EdgeType.REQUIRES: RequiresEdge,
    EdgeType.MAPS_TO_SKILL: MapsToSkillEdge,
    EdgeType.MAPS_TO_TOOL: MapsToToolEdge,
    EdgeType.APPLIED_TO: AppliedToEdge,
    EdgeType.HAS_CASE: HasCaseEdge,
    EdgeType.HAS_STAR_STORY: HasStarStoryEdge,
    EdgeType.BELONGS_TO_PROJECT: BelongsToProjectEdge,
}


# ============================
# HELPER FUNCTIONS
# ============================

def create_node(node_type: NodeType, **kwargs) -> BaseNode:
    """Factory function to create a node by type."""
    model_class = NODE_REGISTRY.get(node_type)
    if not model_class:
        raise ValueError(f"Unknown node type: {node_type}")
    return model_class(**kwargs)


def create_edge(edge_type: EdgeType, source_id: str, target_id: str, **kwargs) -> BaseEdge:
    """Factory function to create an edge by type."""
    model_class = EDGE_REGISTRY.get(edge_type)
    if not model_class:
        raise ValueError(f"Unknown edge type: {edge_type}")
    return model_class(source_id=source_id, target_id=target_id, **kwargs)


def get_node_type(node: BaseNode) -> NodeType:
    """Extract node type from instance."""
    return node.type


def get_edge_type(edge: BaseEdge) -> EdgeType:
    """Extract edge type from instance."""
    return edge.type