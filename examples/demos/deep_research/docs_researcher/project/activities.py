"""Activity-based tools for docs research: web search and docs page fetcher."""
import os
import re

from temporalio import activity
import httpx

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


def _html_to_text(html: str) -> str:
    """Basic HTML to text conversion."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#39;", "'", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@activity.defn
async def web_search(query: str) -> str:
    """Search the web using Tavily and return results from multiple sources.

    Args:
        query: The search query to look up on the web.
    """
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return "Error: TAVILY_API_KEY not set"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "max_results": 5,
                },
            )
            if response.status_code != 200:
                return f"Search API error: {response.status_code}"

            data = response.json()
            answer = data.get("answer", "")

            results = []
            for r in data.get("results", [])[:5]:
                title = r.get("title", "")
                content = r.get("content", "")
                url = r.get("url", "")
                results.append(f"**{title}**\n{content}\nSource: {url}")

            output = f"Search results for '{query}':\n\n"
            if answer:
                output += f"**Summary:** {answer}\n\n---\n\n"
            output += "\n\n---\n\n".join(results)
            return output

    except Exception as e:
        return f"Error searching: {str(e)}"


@activity.defn
async def fetch_docs_page(url: str) -> str:
    """Fetch and parse a documentation page.

    Args:
        url: The full URL of the documentation page to fetch. Use one of:
             https://agentex.sgp.scale.com/docs/... (official docs),
             https://deepwiki.com/scaleapi/scale-agentex/... (platform DeepWiki),
             https://deepwiki.com/scaleapi/scale-agentex-python/... (SDK DeepWiki)
    """
    url = url.strip()

    # Update these allowed prefixes to match your documentation sources
    allowed_prefixes = [
        "https://agentex.sgp.scale.com/",
        "https://deepwiki.com/scaleapi/scale-agentex",
    ]
    if not any(url.startswith(prefix) for prefix in allowed_prefixes):
        return f"Error: URL must be from an allowed documentation source. Got: {url}"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return f"Error fetching {url}: HTTP {response.status_code}"

            content_type = response.headers.get("content-type", "")
            if "json" in content_type:
                return response.text[:10000]

            text = _html_to_text(response.text)
            if len(text) > 15000:
                text = text[:15000] + "\n\n[... truncated, page is very long ...]"
            return f"Content from {url}:\n\n{text}"

    except Exception as e:
        return f"Error fetching {url}: {str(e)}"
