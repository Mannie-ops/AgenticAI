"""Multi-agent technical blogger built with Google Agent Development Kit."""

import datetime
import os

from dotenv import load_dotenv
from google.adk.agents import Agent, LoopAgent
from google.adk.tools import agent_tool

load_dotenv()
MODEL = "gemini-2.5-flash"

# Planner: turns the user's topic into a structured outline.
blog_planner = Agent(
    name="BlogPlanner",
    model=MODEL,
    description="Creates a practical, skimmable outline in Markdown.",
    instruction="""
You are a technical content strategist. Produce a clear Markdown outline with:
- Title
- Short introduction
- 4-6 main sections (each with 2-3 bullets)
- Conclusion

If `codebase_context` exists in state, weave in specific sections or snippets.
Return only the outline in Markdown. If the previous validation feedback is
available, use it to correct the outline.
""",
    output_key="blog_outline",
)


class OutlineValidationChecker(Agent):
    """Checks that the generated outline contains the required structure."""

    def __init__(self):
        super().__init__(
            name="OutlineValidationChecker",
            model=MODEL,
            description="Validates that the outline is usable.",
            instruction="""
Check the outline in state `blog_outline`. It must contain a title, a short
introduction, 4-6 main sections with 2-3 bullets each, and a conclusion.
If all requirements are met, respond exactly "ok". Otherwise respond
"retry" and list the missing pieces clearly so the planner can correct them.
""",
            output_key="validation_result",
        )


robust_blog_planner = LoopAgent(
    name="RobustBlogPlanner",
    description="Runs the planner and outline checker for up to three passes.",
    sub_agents=[blog_planner, OutlineValidationChecker()],
    max_iterations=3,
)

# Writer: expands the approved outline into a full technical article.
blog_writer = Agent(
    name="BlogWriter",
    model=MODEL,
    description="Writes a technical blog post from the approved outline.",
    instruction="""
Write a complete Markdown article from the outline in state `blog_outline`.
Use any available validation feedback to improve the draft.

Guidelines:
- Audience: software engineers; skip basics and focus on practical insight.
- Explain both the how and why.
- Include concise code snippets when helpful.
- Follow the outline's structure with clear H2/H3 headings.
- Include an introduction and conclusion.
- Output only the final article in Markdown (no outer code fence).
""",
    output_key="blog_post",
)


class BlogPostValidationChecker(Agent):
    """Checks the article for completeness and technical clarity."""

    def __init__(self):
        super().__init__(
            name="BlogPostValidationChecker",
            model=MODEL,
            description="Validates the final blog post.",
            instruction="""
Check `blog_post` for an introduction, clear sections matching the outline,
a conclusion, and technical clarity. If it passes, respond exactly "ok".
Otherwise respond "retry" and list the specific fixes needed.
""",
            output_key="validation_result",
        )


robust_blog_writer = LoopAgent(
    name="RobustBlogWriter",
    description="Runs the writer and article checker for up to three passes.",
    sub_agents=[blog_writer, BlogPostValidationChecker()],
    max_iterations=3,
)

# Expose each multi-agent workflow as a callable tool for the root agent.
planner_tool = agent_tool.AgentTool(agent=robust_blog_planner)
writer_tool = agent_tool.AgentTool(agent=robust_blog_writer)

# Root agent coordinates the two workflows.
root_agent = Agent(
    name="Blogger",
    model=MODEL,
    description="A multi-agent blogger that plans, writes, and validates articles.",
    instruction=f"""
When the user provides a blog topic:
1. Call the planner_tool to create and validate the outline.
2. Call the writer_tool to write and validate the full article from that outline.
3. Present the final article, then provide 3 alternative titles and 2
   tweet-length promotional hooks.

Do not skip either tool. If validation feedback is available, incorporate it
in the next generation pass. Be clear and practical.

Date: {datetime.datetime.now().strftime('%Y-%m-%d')}
""",
    tools=[planner_tool, writer_tool],
)
