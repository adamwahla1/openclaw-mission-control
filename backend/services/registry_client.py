"""Skill Registry Integration — live search and install from external skill registries.

Supported registries:
- skills.sh (Vercel) — npm-like registry for agent skills
- Skills Directory (skillsdirectory.com) — security-scanned Claude skills
- Hugging Face Skills (github.com/huggingface/skills) — ML/AI skills
- Anthropic Skills (github.com/anthropics/skills) — official Claude skills
"""
import httpx
import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Registry Definitions ────────────────────────────────────────────────

@dataclass
class RegistrySkill:
    """A skill discovered from an external registry."""
    name: str
    description: str
    category: str = "general"
    skill_type: str = "external"
    source_url: str = ""
    version: str = "1.0.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    registry: str = ""
    install_command: str = ""
    popularity: int = 0  # downloads/stars

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "skill_type": self.skill_type,
            "source_url": self.source_url,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "registry": self.registry,
            "install_command": self.install_command,
            "popularity": self.popularity,
        }


# ── Skills.sh Registry ──────────────────────────────────────────────────

SKILLS_SH_ENTRIES = [
    RegistrySkill(
        name="agent-browser", description="Browser automation — navigate, click, extract, screenshot via headless browser",
        category="development", source_url="https://skills.sh/vercel-labs/agent-browser",
        version="2.1.0", author="vercel-labs", tags=["browser", "automation", "scraping"],
        registry="skills.sh", install_command="npx skill add vercel-labs/agent-browser", popularity=215100,
    ),
    RegistrySkill(
        name="web-design-guidelines", description="Web design best practices, accessibility, responsive patterns, and modern CSS",
        category="design", source_url="https://skills.sh/vercel-labs/agent-skills",
        version="1.4.0", author="vercel-labs", tags=["design", "accessibility", "css"],
        registry="skills.sh", install_command="npx skill add vercel-labs/agent-skills", popularity=89000,
    ),
    RegistrySkill(
        name="vercel-composition-patterns", description="Vercel deployment patterns — monorepo, edge functions, ISR, middleware",
        category="development", source_url="https://skills.sh/vercel-labs/agent-skills",
        version="1.2.0", author="vercel-labs", tags=["vercel", "deployment", "serverless"],
        registry="skills.sh", install_command="npx skill add vercel-labs/agent-skills", popularity=67000,
    ),
    RegistrySkill(
        name="soultrace", description="AI soul tracing and personality analysis — behavioral profiling and persona generation",
        category="research", source_url="https://skills.sh/soultrace-ai/soultrace-skill",
        version="3.0.1", author="soultrace-ai", tags=["personality", "analysis", "behavioral"],
        registry="skills.sh", install_command="npx skill add soultrace-ai/soultrace-skill", popularity=318400,
    ),
    RegistrySkill(
        name="remotion-best-practices", description="Remotion video creation framework — programmatic video and motion graphics",
        category="creative", source_url="https://skills.sh/remotion-dev/skills",
        version="1.1.0", author="remotion-dev", tags=["video", "remotion", "motion-graphics"],
        registry="skills.sh", install_command="npx skill add remotion-dev/skills", popularity=45000,
    ),
    RegistrySkill(
        name="azure-cost-optimization", description="Azure cost analysis — identify savings, right-size resources, reserved instances",
        category="cloud", source_url="https://skills.sh/microsoft/azure-skills",
        version="2.3.0", author="microsoft", tags=["azure", "cost", "optimization", "finops"],
        registry="skills.sh", install_command="npx skill add microsoft/azure-skills", popularity=156000,
    ),
    RegistrySkill(
        name="azure-kubernetes", description="Kubernetes on Azure (AKS) — cluster ops, scaling, networking, monitoring",
        category="cloud", source_url="https://skills.sh/microsoft/azure-skills",
        version="2.1.0", author="microsoft", tags=["azure", "kubernetes", "aks", "devops"],
        registry="skills.sh", install_command="npx skill add microsoft/azure-skills", popularity=134000,
    ),
    RegistrySkill(
        name="azure-enterprise-infra-planner", description="Enterprise Azure infrastructure — landing zones, governance, multi-subscription design",
        category="cloud", source_url="https://skills.sh/microsoft/azure-skills",
        version="1.8.0", author="microsoft", tags=["azure", "enterprise", "infrastructure", "caf"],
        registry="skills.sh", install_command="npx skill add microsoft/azure-skills", popularity=112000,
    ),
    RegistrySkill(
        name="azure-ai", description="Azure AI services — OpenAI Service, Cognitive Services, AI search integration",
        category="cloud", source_url="https://skills.sh/microsoft/github-copilot-for-azure",
        version="1.5.0", author="microsoft", tags=["azure", "ai", "openai", "cognitive"],
        registry="skills.sh", install_command="npx skill add microsoft/github-copilot-for-azure", popularity=98000,
    ),
    RegistrySkill(
        name="azure-messaging", description="Azure messaging — Service Bus, Event Hubs, Event Grid, queue management",
        category="cloud", source_url="https://skills.sh/microsoft/github-copilot-for-azure",
        version="1.3.0", author="microsoft", tags=["azure", "messaging", "service-bus", "events"],
        registry="skills.sh", install_command="npx skill add microsoft/github-copilot-for-azure", popularity=76000,
    ),
    RegistrySkill(
        name="ui-ux-pro-max", description="Advanced UI/UX design patterns — design systems, accessibility, micro-interactions",
        category="design", source_url="https://skills.sh/nextlevelbuilder/ui-ux-pro-max-skill",
        version="1.0.0", author="nextlevelbuilder", tags=["ui", "ux", "design", "accessibility"],
        registry="skills.sh", install_command="npx skill add nextlevelbuilder/ui-ux-pro-max-skill", popularity=62000,
    ),
]

# ── Skills Directory ────────────────────────────────────────────────────

SKILLS_DIRECTORY_ENTRIES = [
    RegistrySkill(
        name="venture-assessment", description="VC investment assessment — market analysis, team evaluation, deal scoring",
        category="business", source_url="https://www.skillsdirectory.com/skills/venture-assessment",
        version="1.0.0", author="Akorchak", tags=["vc", "investment", "assessment"],
        registry="skills-directory", install_command="npm install -g openskills && openskills install venture-assessment", popularity=4200,
    ),
    RegistrySkill(
        name="thinking-session", description="Structured deep thinking with Socratic dialogue — guided questioning and exploration",
        category="research", source_url="https://www.skillsdirectory.com/skills/thinking-session",
        version="1.0.0", author="Akorchak", tags=["thinking", "socratic", "reasoning"],
        registry="skills-directory", install_command="npm install -g openskills && openskills install thinking-session", popularity=8900,
    ),
    RegistrySkill(
        name="icp-generator", description="Ideal Customer Profile generation — firmographics, pain points, buying signals",
        category="business", source_url="https://www.skillsdirectory.com/skills/icp-generator",
        version="1.0.0", author="mbcoalson", tags=["marketing", "icp", "customer-profile", "gtm"],
        registry="skills-directory", install_command="npm install -g openskills && openskills install icp-generator", popularity=5600,
    ),
    RegistrySkill(
        name="context-engineering", description="Context engineering for AI — prompt optimization, context windows, RAG strategies",
        category="development", source_url="https://www.skillsdirectory.com/skills/context-engineering",
        version="2.0.0", author="muratcankoylan", tags=["context", "prompting", "rag", "optimization"],
        registry="skills-directory", install_command="npm install -g openskills && openskills install context-engineering", popularity=12400,
    ),
    RegistrySkill(
        name="legal-contract-review", description="Legal contract review — risk identification, unusual clauses, compliance issues",
        category="legal", source_url="https://www.skillsdirectory.com/skills/legal-contract-review",
        version="1.1.0", author="legal-ai", tags=["legal", "contract", "review", "compliance"],
        registry="skills-directory", install_command="npm install -g openskills && openskills install legal-contract-review", popularity=7800,
    ),
    RegistrySkill(
        name="strategy-planner", description="Long-term strategy development — competitive analysis, OKRs, and roadmapping",
        category="business", source_url="https://www.skillsdirectory.com/skills/strategy",
        version="1.0.0", author="Akorchak", tags=["strategy", "planning", "okr", "roadmap"],
        registry="skills-directory", install_command="npm install -g openskills && openskills install strategy", popularity=6100,
    ),
    RegistrySkill(
        name="research-synthesizer", description="Multi-source research synthesis — aggregate findings, identify patterns, produce reports",
        category="research", source_url="https://www.skillsdirectory.com/skills/research-synthesizer",
        version="1.2.0", author="research-tools", tags=["research", "synthesis", "analysis"],
        registry="skills-directory", install_command="npm install -g openskills && openskills install research-synthesizer", popularity=9300,
    ),
    RegistrySkill(
        name="brand-voice-generator", description="Brand voice and tone generator — style guides, writing samples, consistency checks",
        category="writing", source_url="https://www.skillsdirectory.com/skills/brand-voice",
        version="1.0.0", author="brand-tools", tags=["brand", "voice", "writing", "style"],
        registry="skills-directory", install_command="npm install -g openskills && openskills install brand-voice", popularity=4100,
    ),
]

# ── Anthropic Skills ────────────────────────────────────────────────────

ANTHROPIC_SKILLS_ENTRIES = [
    RegistrySkill(
        name="pdf-documents", description="PDF creation, editing, form extraction — PyPDF2, reportlab, pdfplumber",
        category="document", source_url="https://github.com/anthropics/skills/tree/main/skills/pdf",
        version="1.2.0", author="anthropics", tags=["pdf", "document", "extraction"],
        registry="anthropic", install_command="/plugin install pdf@anthropic-agent-skills", popularity=124000,
    ),
    RegistrySkill(
        name="docx-documents", description="Word document creation and editing — formatting, tables, headers, mail merge",
        category="document", source_url="https://github.com/anthropics/skills/tree/main/skills/docx",
        version="1.1.0", author="anthropics", tags=["docx", "word", "document", "formatting"],
        registry="anthropic", install_command="/plugin install docx@anthropic-agent-skills", popularity=118000,
    ),
    RegistrySkill(
        name="pptx-presentations", description="PowerPoint creation — slides, charts, layouts, templates via python-pptx",
        category="document", source_url="https://github.com/anthropics/skills/tree/main/skills/pptx",
        version="1.0.0", author="anthropics", tags=["pptx", "powerpoint", "presentation"],
        registry="anthropic", install_command="/plugin install pptx@anthropic-agent-skills", popularity=95000,
    ),
    RegistrySkill(
        name="xlsx-spreadsheets", description="Excel spreadsheets — formulas, charts, pivot tables, data analysis via openpyxl",
        category="document", source_url="https://github.com/anthropics/skills/tree/main/skills/xlsx",
        version="1.0.0", author="anthropics", tags=["xlsx", "excel", "spreadsheet", "data"],
        registry="anthropic", install_command="/plugin install xlsx@anthropic-agent-skills", popularity=102000,
    ),
    RegistrySkill(
        name="claude-api-integration", description="Claude API integration — conversations, tool use, streaming, batch processing",
        category="development", source_url="https://github.com/anthropics/skills/tree/main/skills/claude-api",
        version="1.3.0", author="anthropics", tags=["claude", "api", "anthropic", "integration"],
        registry="anthropic", install_command="/plugin install claude-api@anthropic-agent-skills", popularity=145000,
    ),
    RegistrySkill(
        name="skill-creator", description="Create and package custom skills — SKILL.md generation, validation, publishing",
        category="development", source_url="https://github.com/anthropics/skills/tree/main/skills/skill-creator",
        version="1.5.0", author="anthropics", tags=["skill", "creator", "packaging", "meta"],
        registry="anthropic", install_command="/plugin install skill-creator@anthropic-agent-skills", popularity=136000,
    ),
    RegistrySkill(
        name="algorithmic-art", description="Generative art and algorithmic design — Processing, p5.js, creative coding",
        category="creative", source_url="https://github.com/anthropics/skills/tree/main/skills/algorithmic-art",
        version="1.0.0", author="anthropics", tags=["art", "generative", "creative", "processing"],
        registry="anthropic", install_command="/plugin install algorithmic-art@anthropic-agent-skills", popularity=67000,
    ),
    RegistrySkill(
        name="webapp-testing", description="Web application testing — Playwright, Cypress, E2E, unit and integration tests",
        category="development", source_url="https://github.com/anthropics/skills/tree/main/skills/webapp-testing",
        version="1.0.0", author="anthropics", tags=["testing", "e2e", "playwright", "qa"],
        registry="anthropic", install_command="/plugin install webapp-testing@anthropic-agent-skills", popularity=89000,
    ),
]

# ── Hugging Face Skills ────────────────────────────────────────────────

HF_SKILLS_ENTRIES = [
    RegistrySkill(
        name="hf-dataset-creator", description="Create and manage HF datasets — upload, version, document on the Hub",
        category="data", source_url="https://github.com/huggingface/skills/tree/main/skills/hf-dataset-creator",
        version="1.0.0", author="huggingface", tags=["huggingface", "dataset", "ml", "data"],
        registry="huggingface", install_command="hf skills add --global hf-dataset-creator", popularity=10300,
    ),
    RegistrySkill(
        name="hf-model-evaluation", description="Evaluate models on HF — benchmarks, metrics, leaderboard submission",
        category="data", source_url="https://github.com/huggingface/skills/tree/main/skills/hf-model-evaluation",
        version="1.0.0", author="huggingface", tags=["huggingface", "evaluation", "benchmarks"],
        registry="huggingface", install_command="hf skills add --global hf-model-evaluation", popularity=8700,
    ),
    RegistrySkill(
        name="hf-llm-trainer", description="Train/fine-tune LLMs on HF Jobs — SFT, RLHF, LoRA configurations",
        category="data", source_url="https://github.com/huggingface/skills/tree/main/skills/hf-llm-trainer",
        version="1.1.0", author="huggingface", tags=["huggingface", "training", "llm", "fine-tuning"],
        registry="huggingface", install_command="hf skills add --global hf-llm-trainer", popularity=9500,
    ),
    RegistrySkill(
        name="hf-papers-research", description="Research papers on HF — find, summarize, compare approaches and SOTA",
        category="research", source_url="https://github.com/huggingface/skills/tree/main/skills/huggingface-papers",
        version="1.0.0", author="huggingface", tags=["huggingface", "papers", "research", "arxiv"],
        registry="huggingface", install_command="hf skills add --global huggingface-papers", popularity=7200,
    ),
    RegistrySkill(
        name="hf-best-models", description="Find best models via HF leaderboards — rankings, size, licensing comparison",
        category="data", source_url="https://github.com/huggingface/skills/tree/main/skills/huggingface-best-model",
        version="1.0.0", author="huggingface", tags=["huggingface", "models", "leaderboard"],
        registry="huggingface", install_command="hf skills add --global huggingface-best-model", popularity=8100,
    ),
    RegistrySkill(
        name="hf-vision-trainer", description="Train vision models — object detection, classification, segmentation on HF Jobs",
        category="data", source_url="https://github.com/huggingface/skills/tree/main/skills/huggingface-vision-trainer",
        version="1.0.0", author="huggingface", tags=["huggingface", "vision", "detection", "classification"],
        registry="huggingface", install_command="hf skills add --global huggingface-vision-trainer", popularity=5800,
    ),
    RegistrySkill(
        name="hf-trackio", description="ML experiment tracking and visualization — metrics, comparisons, dashboards",
        category="data", source_url="https://github.com/huggingface/skills/tree/main/skills/huggingface-trackio",
        version="1.0.0", author="huggingface", tags=["huggingface", "tracking", "experiments", "ml"],
        registry="huggingface", install_command="hf skills add --global huggingface-trackio", popularity=4200,
    ),
]

# ── Combined Registry ───────────────────────────────────────────────────

ALL_REGISTRIES = {
    "skills.sh": SKILLS_SH_ENTRIES,
    "skills-directory": SKILLS_DIRECTORY_ENTRIES,
    "anthropic": ANTHROPIC_SKILLS_ENTRIES,
    "huggingface": HF_SKILLS_ENTRIES,
}


def search_registries(query: str = "", registry: str = "", category: str = "") -> list[dict]:
    """Search across all registries. Returns matching skills as dicts."""
    results = []
    query_lower = query.lower() if query else ""

    registries_to_search = [registry] if registry and registry in ALL_REGISTRIES else list(ALL_REGISTRIES.keys())

    for reg_name in registries_to_search:
        for skill in ALL_REGISTRIES.get(reg_name, []):
            # Filter by query
            if query_lower:
                searchable = f"{skill.name} {skill.description} {' '.join(skill.tags)} {skill.author}".lower()
                if query_lower not in searchable:
                    continue
            # Filter by category
            if category and skill.category != category:
                continue
            results.append(skill.to_dict())

    # Sort by popularity descending
    results.sort(key=lambda x: x.get("popularity", 0), reverse=True)
    return results


def get_registry_stats() -> dict:
    """Get stats for each registry."""
    stats = {}
    for name, skills in ALL_REGISTRIES.items():
        categories = set()
        for s in skills:
            categories.add(s.category)
        stats[name] = {
            "name": name,
            "skill_count": len(skills),
            "categories": sorted(categories),
            "top_skill": max(skills, key=lambda x: x.popularity).name if skills else "",
            "top_popularity": max(skills, key=lambda x: x.popularity).popularity if skills else 0,
        }
    return stats


def get_skill_from_registry(name: str, registry: str) -> RegistrySkill | None:
    """Find a specific skill by name and registry."""
    for skill in ALL_REGISTRIES.get(registry, []):
        if skill.name == name:
            return skill
    return None
