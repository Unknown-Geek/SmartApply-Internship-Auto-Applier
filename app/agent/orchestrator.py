# =============================================================================
# SmartApply — Autonomous Internship Application Orchestrator
# =============================================================================
# High-level orchestration layer that uses the Gemini agent with Playwright
# browser automation to autonomously search for internships, analyze listings,
# fill forms, and submit applications.
#
# Each workflow is a series of agent "turns", with state tracked in SQLite.
# =============================================================================

import asyncio
import json
import uuid
from typing import Optional

from app.agent.cerebras_agent import CerebrasAgent, AgentResult
from app.agent.human_loop import HumanLoop
from app.config import get_settings
from app.db.database import (
    add_job, get_jobs, update_job_status,
    create_application, update_application,
    get_all_profile, recall_as_context, remember,
)


# =============================================================================
# Prompt Templates
# =============================================================================

SEARCH_PROMPT = """You are SmartApply, an autonomous internship application agent.

TASK: Search for internship listings matching the user's criteria.

{memory_context}

USER PROFILE:
{profile_context}

SEARCH CRITERIA:
{criteria}

INSTRUCTIONS:
1. Use browse_url to navigate to job boards (LinkedIn Jobs, Indeed, Glassdoor, Internshala, etc.)
2. Search for internships matching the criteria
3. For each listing found, extract:
   - Job title
   - Company name
   - Location (or "Remote")
   - Application URL
   - Brief description
   - Date posted (if available)
4. Return results as a JSON array:

```json
[
  {{
    "title": "Software Engineering Intern",
    "company": "Example Corp",
    "url": "https://...",
    "location": "Remote",
    "description": "Brief description...",
    "date_posted": "2026-02-20",
    "source": "LinkedIn"
  }}
]
```

Return ONLY the JSON array. Find at least 5 listings if available.
"""

ANALYZE_PROMPT = """You are SmartApply, an autonomous internship application agent.

TASK: Analyze an internship application page and determine what information is needed.

{memory_context}

JOB DETAILS:
- Title: {title}
- Company: {company}
- URL: {url}

INSTRUCTIONS:
1. Use browse_url to navigate to {url}
2. Use extract_page_data to analyze the application form/page
3. Identify all required fields, optional fields, and any file upload requirements
4. Determine if this is a direct application form, a redirect to an ATS, or requires login
5. Return a JSON object:

```json
{{
  "application_type": "direct_form|ats_redirect|requires_login|external_link",
  "ats_name": "Workday|Lever|Greenhouse|etc.",
  "fields": [
    {{
      "name": "field_name",
      "type": "text|email|file|select|textarea|checkbox",
      "required": true,
      "label": "Full Name",
      "selector": "CSS selector if identifiable"
    }}
  ],
  "requires_resume": true,
  "requires_cover_letter": false,
  "requires_login": false,
  "notes": "Any additional observations"
}}
```

Return ONLY the JSON object.
"""

APPLY_PROMPT = """You are SmartApply, an autonomous internship application agent.

TASK: Complete and submit an internship application.

{memory_context}

USER PROFILE:
{profile_context}

JOB DETAILS:
- Title: {title}
- Company: {company}
- URL: {url}

APPLICATION FORM ANALYSIS:
{form_analysis}

INSTRUCTIONS:
1. Use browse_url to navigate to {url}
2. Use extract_page_data to see the form fields
3. Use fill_form to fill each field with the user's profile information
4. Use upload_file if resume upload is required
5. Use take_screenshot before submission to verify
6. Use click_element to submit the application
7. After submission, verify success by checking for confirmation messages

IMPORTANT RULES:
- Be careful and accurate with all information
- If you encounter a CAPTCHA you cannot solve, report it
- If the form requires information not in the profile, use reasonable defaults
- Do NOT submit if critical required fields cannot be filled
- Take a screenshot before and after submission

Return a JSON object:
```json
{{
  "status": "success|partial|failed|blocked",
  "steps_taken": ["Navigated to URL", "Filled name field", ...],
  "confirmation_message": "Thank you for applying...",
  "issues": ["Could not upload resume", ...],
  "screenshot_taken": true
}}
```

Return ONLY the JSON object.
"""

RESUME_CONTEXT_PROMPT = """You are SmartApply, an autonomous internship application agent.

TASK: Learn and remember key facts from the user's resume/profile for future applications.

{resume_text}

Extract and organize the following information:
1. Full name
2. Email
3. Phone
4. Education (university, degree, GPA, year)
5. Skills (technical and soft)
6. Experience (positions, companies, dates)
7. Projects
8. Certifications
9. Links (LinkedIn, GitHub, portfolio)

Return a JSON object with category keys:

```json
{{
  "personal": {{"name": "...", "email": "...", "phone": "..."}},
  "education": {{"university": "...", "degree": "...", "major": "...", "gpa": "...", "graduation": "..."}},
  "skills": ["Python", "JavaScript", ...],
  "experience": [{{"title": "...", "company": "...", "dates": "...", "description": "..."}}],
  "projects": [{{"name": "...", "description": "...", "tech": "..."}}],
  "certifications": ["..."],
  "links": {{"linkedin": "...", "github": "...", "portfolio": "..."}}
}}
```

Return ONLY the JSON object.
"""


# =============================================================================
# Orchestrator Class
# =============================================================================

class SmartApplyOrchestrator:
    """
    Orchestrates the full internship auto-application pipeline:
    1. Profile ingestion — learns user data from resume
    2. Job search — finds relevant internship listings
    3. Job analysis — analyzes each application page
    4. Application — fills and submits applications
    5. Tracking — records everything in SQLite
    """

    def __init__(
        self,
        thinking: str = "medium",
        timeout: int = 600,
        max_steps: int = 25,
        human_loop: Optional[HumanLoop] = None,
    ):
        self.thinking = thinking
        self.timeout = timeout
        self.max_steps = max_steps
        self.human_loop = human_loop

    def _create_agent(self, max_turns: int = None) -> CerebrasAgent:
        """Create a configured CerebrasAgent instance."""
        settings = get_settings()
        api_key = settings.effective_api_key
        if not api_key:
            raise RuntimeError("No Cerebras API key configured (set CEREBRAS_API_KEY)")
        return CerebrasAgent(
            api_key=api_key,
            model=settings.cerebras_model,
            temperature=settings.cerebras_temperature,
            base_url=settings.cerebras_base_url,
            headless=settings.headless,
            max_turns=max_turns or self.max_steps,
            timeout_seconds=self.timeout,
            human_loop=self.human_loop,
        )

    # -----------------------------------------------------------------
    # 1) Profile Ingestion
    # -----------------------------------------------------------------

    async def ingest_profile(self, resume_text: str) -> dict:
        """
        Parse a resume / profile text and store structured data in SQLite.

        Args:
            resume_text: Raw text of the user's resume or profile info.

        Returns:
            dict of extracted profile data.
        """
        prompt = RESUME_CONTEXT_PROMPT.format(resume_text=resume_text)

        # Profile ingestion is text-only (no browser needed), but we
        # still use the agent for consistent Gemini interaction.
        agent = self._create_agent(max_turns=3)
        result = await agent.run(prompt, task_type="profile_ingestion")

        if not result.success:
            return {"error": result.error}

        data = _safe_parse_json(result.text)
        if not data:
            return {"error": "Could not parse profile data", "raw": result.text}

        # Store in memory and profile tables
        from app.db.database import set_profile

        if "personal" in data:
            for k, v in data["personal"].items():
                set_profile(k, str(v))
                remember("personal", k, str(v), source="resume")

        if "education" in data:
            for k, v in data["education"].items():
                set_profile(f"education_{k}", str(v))
                remember("education", k, str(v), source="resume")

        if "skills" in data:
            set_profile("skills", json.dumps(data["skills"]))
            remember("skills", "list", ", ".join(data["skills"]), source="resume")

        if "experience" in data:
            set_profile("experience", json.dumps(data["experience"]))
            for i, exp in enumerate(data["experience"]):
                remember("experience", f"position_{i}",
                         f"{exp.get('title', '')} at {exp.get('company', '')}",
                         source="resume")

        if "links" in data:
            for k, v in data["links"].items():
                set_profile(f"link_{k}", str(v))
                remember("links", k, str(v), source="resume")

        if "projects" in data:
            set_profile("projects", json.dumps(data["projects"]))
            for i, proj in enumerate(data["projects"]):
                remember("projects", f"project_{i}",
                         f"{proj.get('name', '')}: {proj.get('description', '')}",
                         source="resume")

        return data

    # -----------------------------------------------------------------
    # 2) Job Search
    # -----------------------------------------------------------------

    async def search_jobs(self, criteria: str) -> list[dict]:
        """
        Search for internship listings matching the given criteria.

        Args:
            criteria: Free-text search criteria (role, location, etc.)

        Returns:
            List of job dicts added to the database.
        """
        profile = get_all_profile()
        memory_ctx = recall_as_context(["personal", "education", "skills"])

        prompt = SEARCH_PROMPT.format(
            criteria=criteria,
            profile_context=json.dumps(profile, indent=2) if profile else "Not yet configured.",
            memory_context=f"KNOWN FACTS:\n{memory_ctx}" if memory_ctx else "",
        )

        agent = self._create_agent()
        result = await agent.run(prompt, task_type="job_search")

        if not result.success:
            return [{"error": result.error}]

        jobs = _safe_parse_json(result.text)
        if not isinstance(jobs, list):
            return [{"error": "Could not parse job listings", "raw": result.text}]

        saved_jobs = []
        for job in jobs:
            try:
                job_id = add_job(
                    title=job.get("title", "Unknown"),
                    company=job.get("company", "Unknown"),
                    url=job.get("url", ""),
                    location=job.get("location"),
                    description=job.get("description"),
                    source=job.get("source"),
                    date_posted=job.get("date_posted"),
                    external_id=job.get("external_id"),
                    metadata=job,
                )
                if job_id:
                    job["id"] = job_id
                    saved_jobs.append(job)
            except Exception:
                continue

        return saved_jobs

    # -----------------------------------------------------------------
    # 3) Job Analysis
    # -----------------------------------------------------------------

    async def analyze_job(self, job_id: int) -> dict:
        """
        Analyze a specific job's application page.

        Args:
            job_id: Database id of the job to analyze.

        Returns:
            dict with form analysis results.
        """
        jobs = get_jobs()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            return {"error": f"Job {job_id} not found"}

        memory_ctx = recall_as_context()

        prompt = ANALYZE_PROMPT.format(
            title=job["title"],
            company=job["company"],
            url=job["url"],
            memory_context=f"KNOWN FACTS:\n{memory_ctx}" if memory_ctx else "",
        )

        agent = self._create_agent()
        result = await agent.run(prompt, task_type="job_analysis")

        if not result.success:
            return {"error": result.error}

        analysis = _safe_parse_json(result.text)
        if not analysis:
            return {"error": "Could not parse analysis", "raw": result.text}

        # Remember findings about this company's application process
        remember(
            "applications",
            f"{job['company']}_ats",
            analysis.get("ats_name", "unknown"),
            source=f"job_{job_id}",
        )

        update_job_status(job_id, "queued")
        return analysis

    # -----------------------------------------------------------------
    # 4) Apply to Job
    # -----------------------------------------------------------------

    async def apply_to_job(self, job_id: int, form_analysis: dict = None) -> dict:
        """
        Attempt to apply to a specific job.

        Args:
            job_id: Database id of the job.
            form_analysis: Optional pre-computed form analysis.

        Returns:
            dict with application result.
        """
        jobs = get_jobs()
        job = next((j for j in jobs if j["id"] == job_id), None)
        if not job:
            return {"error": f"Job {job_id} not found"}

        # Analyze first if not already done
        if not form_analysis:
            form_analysis = await self.analyze_job(job_id)
            if "error" in form_analysis:
                return form_analysis

        update_job_status(job_id, "applying")
        session_id = f"apply-{job_id}-{uuid.uuid4().hex[:8]}"
        app_id = create_application(job_id, session_id)

        profile = get_all_profile()
        memory_ctx = recall_as_context()

        prompt = APPLY_PROMPT.format(
            title=job["title"],
            company=job["company"],
            url=job["url"],
            form_analysis=json.dumps(form_analysis, indent=2),
            profile_context=json.dumps(profile, indent=2) if profile else "No profile data.",
            memory_context=f"KNOWN FACTS:\n{memory_ctx}" if memory_ctx else "",
        )

        agent = self._create_agent()
        result = await agent.run(
            prompt,
            task_type="apply",
            session_id=session_id,
        )

        if not result.success:
            update_application(app_id, "error", error=result.error)
            update_job_status(job_id, "failed")
            return {"error": result.error, "application_id": app_id}

        app_result = _safe_parse_json(result.text)
        if not app_result:
            app_result = {"status": "partial", "raw": result.text}

        status = app_result.get("status", "partial")
        steps = app_result.get("steps_taken", [])

        if status == "success":
            update_application(app_id, "success", steps=steps)
            update_job_status(job_id, "applied")
        elif status == "partial":
            update_application(app_id, "partial", steps=steps)
            update_job_status(job_id, "failed")
        else:
            update_application(
                app_id, "failed", steps=steps,
                error=app_result.get("issues", []),
            )
            update_job_status(job_id, "failed")

        return {
            "application_id": app_id,
            "status": status,
            "steps": steps,
            "confirmation": app_result.get("confirmation_message"),
            "issues": app_result.get("issues", []),
        }

    # -----------------------------------------------------------------
    # 5) Batch Apply Pipeline
    # -----------------------------------------------------------------

    async def run_pipeline(
        self,
        criteria: str,
        max_applications: int = 5,
        auto_apply: bool = False,
    ) -> dict:
        """
        Run the full search → analyze → apply pipeline.

        Args:
            criteria: Search criteria for internships.
            max_applications: Max number of applications to attempt.
            auto_apply: If True, automatically apply after analysis.

        Returns:
            Pipeline summary dict.
        """
        summary = {
            "search_results": 0,
            "analyzed": 0,
            "applied": 0,
            "failed": 0,
            "details": [],
        }

        # Step 1: Search
        jobs = await self.search_jobs(criteria)
        summary["search_results"] = len(jobs)

        if not jobs or "error" in jobs[0]:
            summary["error"] = jobs[0].get("error") if jobs else "No results"
            return summary

        # Step 2: Analyze & optionally apply
        for i, job in enumerate(jobs[:max_applications]):
            job_id = job.get("id")
            if not job_id:
                continue

            detail = {"job_id": job_id, "title": job.get("title"), "company": job.get("company")}

            # Analyze
            analysis = await self.analyze_job(job_id)
            if "error" in analysis:
                detail["status"] = "analysis_failed"
                detail["error"] = analysis["error"]
                summary["failed"] += 1
                summary["details"].append(detail)
                continue

            summary["analyzed"] += 1
            detail["analysis"] = analysis

            # Apply
            if auto_apply:
                result = await self.apply_to_job(job_id, form_analysis=analysis)
                detail["application"] = result
                if result.get("status") == "success":
                    summary["applied"] += 1
                else:
                    summary["failed"] += 1
            else:
                detail["status"] = "analyzed_pending_approval"

            summary["details"].append(detail)

        return summary

    # -----------------------------------------------------------------
    # Run custom agent task (free-form)
    # -----------------------------------------------------------------

    async def run_task(self, task: str) -> AgentResult:
        """Run an arbitrary task through the Cerebras agent with browser tools."""
        memory_ctx = recall_as_context()
        profile = get_all_profile()

        full_prompt = f"""You are SmartApply, an autonomous internship application agent.

KNOWN FACTS:
{memory_ctx if memory_ctx else "None yet."}

USER PROFILE:
{json.dumps(profile, indent=2) if profile else "Not yet configured."}

TASK:
{task}

Complete the task using your available browser tools (browse_url, fill_form, click_element, etc.).
If you need information from the user, use ask_user to ask.
Use notify_user to send progress updates.
"""
        agent = self._create_agent()
        return await agent.run(full_prompt, task_type="custom_task")

    # -----------------------------------------------------------------
    # Apply to a specific URL (triggered from Telegram)
    # -----------------------------------------------------------------

    async def apply_to_url(self, url: str) -> dict:
        """
        Directly apply to an internship at the given URL.
        Triggered by sending a URL to the Telegram bot.
        """
        # Notify user that we're starting
        if self.human_loop:
            await self.human_loop.notify(f"🚀 Starting application for:\n{url}")

        # Add job to database
        job_id = add_job(
            title="(From Telegram)",
            company="(Unknown)",
            url=url,
            source="telegram",
        )

        # Analyze the page first
        analysis = await self.analyze_job(job_id)
        if "error" in analysis:
            if self.human_loop:
                await self.human_loop.notify(f"❌ Could not analyze page: {analysis['error']}")
            return {"error": analysis["error"]}

        if self.human_loop:
            app_type = analysis.get("application_type", "unknown")
            fields_count = len(analysis.get("fields", []))
            await self.human_loop.notify(
                f"📝 Analysis complete:\n"
                f"• Type: {app_type}\n"
                f"• Fields: {fields_count}\n"
                f"• Resume required: {analysis.get('requires_resume', 'unknown')}\n"
                f"\n⚙️ Starting to fill the application..."
            )

        # Apply
        result = await self.apply_to_job(job_id, form_analysis=analysis)

        # Notify result
        if self.human_loop:
            status = result.get("status", "unknown")
            emoji = "✅" if status == "success" else "⚠️" if status == "partial" else "❌"
            msg = f"{emoji} Application {status}\n"
            if result.get("confirmation"):
                msg += f"\n💬 {result['confirmation']}"
            issues = result.get("issues", [])
            if issues:
                msg += f"\n\n⚠️ Issues: {', '.join(str(i) for i in issues)}"
            await self.human_loop.notify(msg)

        return result


# =============================================================================
# Helpers
# =============================================================================

def _safe_parse_json(text: str) -> Optional[dict | list]:
    """Try to extract and parse JSON from agent output."""
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    import re
    match = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding JSON array or object
    for start, end in [("[", "]"), ("{", "}")]:
        idx_start = text.find(start)
        idx_end = text.rfind(end)
        if idx_start >= 0 and idx_end > idx_start:
            try:
                return json.loads(text[idx_start:idx_end + 1])
            except json.JSONDecodeError:
                pass

    return None
