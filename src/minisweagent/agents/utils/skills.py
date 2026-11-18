"""Load reusable prompt skills from markdown files."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class Skill(BaseModel):
    name: str
    path: Path
    root: Path
    content: str


def load_skills(skill_specs: list[str | Path] | None) -> list[Skill]:
    """Load skills from paths, directories with SKILL.md, or names in skills directories."""
    if not skill_specs:
        return []
    skills: list[Skill] = []
    seen: set[Path] = set()
    for spec in skill_specs:
        skill = _load_skill(spec)
        if skill.path in seen:  # the same skill reached via name and path
            continue
        seen.add(skill.path)
        skills.append(skill)
    return skills


def _load_skill(spec: str | Path) -> Skill:
    path = _resolve_skill_path(spec)
    # Skill files are UTF-8; never rely on the platform default (cp936 on a
    # Chinese Windows locale cannot decode most of them).
    content = path.read_text(encoding="utf-8")
    return Skill(
        name=_skill_name(path),
        path=path.resolve(),
        root=path.parent.resolve(),
        content=content,
    )


def _resolve_skill_path(spec: str | Path) -> Path:
    """Resolve a skill spec to its SKILL.md.

    Accepts a markdown file, a directory containing SKILL.md, or a bare skill
    name looked up in the known skills directories.
    """
    spec_path = Path(spec).expanduser()
    tried: list[str] = []

    # A path to the markdown file itself, e.g. `.agents/skills/tdd/SKILL.md`.
    if spec_path.is_file():
        return spec_path
    tried.append(str(spec_path))

    # A directory containing SKILL.md, e.g. `.agents/skills/tdd`.
    md_file_path = spec_path / "SKILL.md"
    if md_file_path.is_file():
        return md_file_path
    tried.append(str(md_file_path))

    # A bare skill name, e.g. `tdd`, looked up in the known skills directories.
    for root in _skill_roots():
        candidate = root / str(spec) / "SKILL.md"
        if candidate.is_file():
            return candidate
        tried.append(str(candidate))

    raise FileNotFoundError(f"Could not find skill {spec!r} (tried: {', '.join(tried)})")


def _skill_roots() -> list[Path]:
    """Directories that hold one subdirectory per named skill."""
    roots: list[Path] = []
    for base in (Path.cwd(), *Path.cwd().parents):
        candidate = base / ".agents" / "skills"
        if candidate.is_dir():
            roots.append(candidate)
            break
    roots.append(Path.home() / ".claude" / "skills")
    return roots


def _skill_name(path: Path) -> str:
    if path.name == "SKILL.md":
        return path.parent.name
    return path.stem


def render_skills(skills: list[Skill]) -> str:
    """Render skills as a compact markdown block for prompt templates."""
    blocks = []
    for skill in skills:
        blocks.append(f"<skill name={skill.name!r} path={str(skill.path)!r}>\n{skill.content.rstrip()}\n</skill>")
    return "\n\n".join(blocks)


def skills_to_template_vars(skills: list[Skill]) -> dict[str, Any]:
    """Return both structured and rendered forms for Jinja templates."""
    return {
        "skills": [skill.model_dump(mode="json") for skill in skills],
        "skills_text": render_skills(skills),
    }


def load_skill_asset(skills: list[Skill], skill_name: str, asset_path: str) -> str:
    skill = next((s for s in skills if s.name == skill_name), None)
    if skill is None:
        raise ValueError(f"Unknown skill: {skill_name}")

    root = skill.root.resolve()
    full_path = (root / asset_path).resolve()

    if not full_path.is_relative_to(root):
        raise ValueError(f"Skill asset path escapes skill root: {asset_path}")

    if not full_path.is_file():
        raise FileNotFoundError(f"Skill asset not found: {skill_name}/{asset_path}")

    return full_path.read_text(encoding="utf-8")



