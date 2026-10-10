import argparse
import json
import os
from datetime import datetime, timezone
from uuid import uuid4
import re 
from pathlib import Path
from urllib.parse import urlparse
import requests
from dotenv import load_dotenv

from app.procurement.discovery_schemas import EvidenceSource

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


class ResearchToolError(RuntimeError):
    pass


def search_web(
    query: str,
    max_results: int = 5,
    *,
    include_domains: list[str] | None = None,
) -> list[EvidenceSource]:
    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    if not 1 <= max_results <= 5:
        raise ValueError("Request between 1 and 5 results.")

    api_key = os.getenv("TAVILY_API_KEY", "").strip()

    if not api_key:
        raise ResearchToolError(
            "TAVILY_API_KEY is missing from the local environment."
        )

    try:
        with requests.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "topic": "general",
                "search_depth": "basic",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
                "auto_parameters": False,
                "include_domains": include_domains or [],
            },
            timeout=(10, 45),
        ) as response:
            if response.status_code != 200:
                raise ResearchToolError(
                    "Search request failed with HTTP "
                    f"{response.status_code}. "
                    "Check your search account and API configuration."
                )

            payload = response.json()

    except requests.RequestException as exc:
        raise ResearchToolError(
            "Search service could not be reached or returned invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise ResearchToolError("Unexpected search response format.")

    results = payload.get("results")

    if not isinstance(results, list):
        raise ResearchToolError("Search response is missing its results.")

    retrieved_at = datetime.now(timezone.utc)
    sources = []
    seen_urls = set()

    for item in results:
        if not isinstance(item, dict):
            continue

        url = item.get("url")
        content = item.get("content")

        if not isinstance(url, str) or not isinstance(content, str):
            continue

        url = url.strip()
        content = content.strip()

        if (
            not url.startswith(("https://", "http://"))
            or not content
            or url in seen_urls
        ):
            continue

        seen_urls.add(url)

        sources.append(
            EvidenceSource(
                source_id=str(uuid4()),
                source_type="other",
                reference=url,
                retrieved_at=retrieved_at,
                excerpt=content,
                title=item.get("title"),
                search_query=query,
                search_score=item.get("score"),
                search_request_id=payload.get("request_id"),
            )
        )

    return sources

def quoted_name(value: str) -> str:
    name = " ".join(value.replace('"', "").split())
    if not name:
        raise ValueError("A location or carrier name cannot be empty.")
    return f'"{name}"'


def normalize(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold()))


def screen_results(
    sources: list[EvidenceSource],
    destination_names: list[str],
) -> list[EvidenceSource]:
    """
    Preliminary relevance screening only.

    Missing keywords do not prove irrelevance: aliases and incomplete
    excerpts can hide useful results. Keep these results for review.
    """
    names = [
        normalize(name)
        for name in destination_names
        if normalize(name)
    ]

    maritime_terms = (
        "port",
        "seaport",
        "terminal",
        "container",
        "shipping",
        "vessel",
        "maritime",
        "schedule",
        "harbour",
        "harbor",
    )

    for source in sources:
        text = normalize(
            f"{source.title or ''} {source.excerpt}"
        )

        mentions_destination = any(
            f" {name} " in f" {text} "
            for name in names
        )
        mentions_shipping = any(
            term in text.split()
            for term in maritime_terms
        )

        source.relevance_status = (
            "potentially_relevant"
            if mentions_destination and mentions_shipping
            else "needs_review"
        )

    return sources


def focused_search(
    queries: list[str],
    destination_names: list[str],
    *,
    official_domain: str | None = None,
) -> list[EvidenceSource]:
    """
    At most two searches per invocation.
    Retry only when the first search has no potential matches.
    """
    domains = None

    if official_domain:
        # Supply only a domain whose ownership has already been checked.
        domain = official_domain.strip().lower()

        if not re.fullmatch(
            r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", domain
        ) or "." not in domain:
            raise ValueError(
                "Use a bare domain, without https:// or a path."
            )

        domains = [domain]

    collected = []

    for query in queries[:2]:
        sources = search_web(query, include_domains=domains)

        if domains:
            # Check returned hosts as well as sending the API filter.
            domain = domains[0]
            sources = [
                source
                for source in sources
                if (
                    (urlparse(source.reference).hostname or "").lower()
                    == domain
                    or (
                        urlparse(source.reference).hostname or ""
                    ).lower().endswith("." + domain)
                )
            ]

        screen_results(sources, destination_names)
        collected.extend(sources)

        if any(
            source.relevance_status == "potentially_relevant"
            for source in sources
        ):
            break

    return collected


def search_port_identity(
    pod: str,
    *,
    aliases: list[str] | None = None,
) -> list[EvidenceSource]:
    destination = quoted_name(pod)

    return focused_search(
        [
            f"{destination} seaport container terminal official location",
            f"{destination} maritime port authority country UN LOCODE",
        ],
        [pod, *(aliases or [])],
    )


def search_carriers(
    pol: str,
    pod: str,
) -> list[EvidenceSource]:
    origin = quoted_name(pol)
    destination = quoted_name(pod)

    return focused_search(
        [
            f"{origin} {destination} container shipping lines services",
            f"{destination} container terminal shipping carriers services",
        ],
        [pod],
    )


def search_route(
    carrier: str,
    pol: str,
    pod: str,
    *,
    official_domain: str | None = None,
) -> list[EvidenceSource]:
    line = quoted_name(carrier)
    origin = quoted_name(pol)
    destination = quoted_name(pod)

    return focused_search(
        [
            f"{line} {origin} {destination} point to point schedule",
            f"{line} {origin} {destination} container service transshipment",
        ],
        [pod],
        official_domain=official_domain,
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    args = parser.parse_args()

    try:
        sources = search_web(args.query)
    except ResearchToolError as exc:
        parser.exit(1, f"Search failed: {exc}\n")

    print(json.dumps(
        [source.model_dump(mode="json") for source in sources],
        indent=2,
        ensure_ascii=False,
    ))