#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("Perplexity Search MCP Server")

# Perplexity API key
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

@mcp.tool(description="Search using Perplexity Search API with web search capability. Returns ranked search results with URLs, titles, snippets, and extracted content.")
def search_perplexity(
    query: str, 
    max_results: int = 5, 
    max_tokens_per_page: int = 1024,
    country: str = None,
    search_domain_filter: list = None
) -> dict:
    """
    Search using Perplexity Search API with web search capability.
    Returns ranked search results with URLs, titles, snippets, and extracted content.
    
    Args:
        query: Search query string
        max_results: Number of results (1-20, default 5)
        max_tokens_per_page: Content extraction limit per page (default 1024)
        country: ISO 3166-1 alpha-2 country code (e.g., "US", "GB")
        search_domain_filter: List of domains to filter results (max 20)
    """
    try:
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "query": query,
            "max_results": min(max(max_results, 1), 20),
            "max_tokens_per_page": max_tokens_per_page
        }
        
        if country:
            payload["country"] = country
        if search_domain_filter:
            payload["search_domain_filter"] = search_domain_filter[:20]
        
        response = requests.post("https://api.perplexity.ai/search", headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        results = data.get("results", [])
        
        # Fetch and extract content from each result URL
        enhanced_results = []
        for result in results:
            url = result.get("url")
            enhanced_result = {
                "title": result.get("title"),
                "url": url,
                "snippet": result.get("snippet"),
                "date": result.get("date"),
                "content": None,
                "content_extraction_status": "not_attempted"
            }
            
            # Fetch webpage content using BeautifulSoup
            if url:
                try:
                    fetch_headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                    page_response = requests.get(url, headers=fetch_headers, timeout=10)
                    page_response.raise_for_status()
                    
                    soup = BeautifulSoup(page_response.text, 'html.parser')
                    
                    # Remove script, style, and other non-content elements
                    for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                        element.decompose()
                    
                    # Try to find main content areas with common selectors
                    main_content = None
                    selectors = [
                        'main', 'article', '[role="main"]',
                        '.content', '#content', '.main-content', '#main-content',
                        '.post-content', '.entry-content', '.article-content',
                        '.page-content', '#page-content', '.post-body', '.article-body',
                        '.content-area', '.site-content', '#site-content',
                        '.blog-post', '.single-post', '.post', '#post',
                        '[itemprop="articleBody"]', '.markdown-body'
                    ]
                    for selector in selectors:
                        content_area = soup.select_one(selector)
                        if content_area:
                            main_content = content_area.get_text(separator=' ', strip=True)
                            break
                    
                    # Fallback to body content if no main area found
                    if not main_content:
                        main_content = soup.get_text(separator=' ', strip=True)
                    
                    # Clean up extra whitespace
                    main_content = ' '.join(main_content.split())
                    
                    enhanced_result["content"] = main_content[:2000]  # First 2000 chars
                    enhanced_result["content_extraction_status"] = "success"
                except Exception as fetch_error:
                    enhanced_result["content_extraction_status"] = f"error: {str(fetch_error)}"
            
            enhanced_results.append(enhanced_result)
        
        return {
            "status": "success",
            "query": query,
            "results": enhanced_results,
            "total_results": len(enhanced_results)
        }
    
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "query": query,
            "error": str(e)
        }

@mcp.tool(description="Fetch and extract main content from a webpage URL")
def fetch_webpage_content(url: str) -> dict:
    """
    Fetch and extract content from a webpage.
    Returns the main content and metadata.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Extract text content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script, style, and other non-content elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
            element.decompose()
        
        # Try to find main content areas
        main_content = None
        selectors = [
            'main', 'article', '[role="main"]',
            '.content', '#content', '.main-content', '#main-content',
            '.post-content', '.entry-content', '.article-content',
            '.page-content', '#page-content', '.post-body', '.article-body',
            '.content-area', '.site-content', '#site-content',
            '.blog-post', '.single-post', '.post', '#post',
            '[itemprop="articleBody"]', '.markdown-body'
        ]
        for selector in selectors:
            content_area = soup.select_one(selector)
            if content_area:
                main_content = content_area.get_text(separator=' ', strip=True)
                break
        
        # Fallback to body content if no main area found
        if not main_content:
            main_content = soup.get_text(separator=' ', strip=True)
        
        # Clean up extra whitespace
        main_content = ' '.join(main_content.split())
        
        return {
            "status": "success",
            "url": url,
            "content": main_content[:5000], 
            "content_length": len(main_content),
            "status_code": response.status_code
        }
    
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "url": url,
            "error": str(e)
        }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"Starting Perplexity MCP server on {host}:{port}")
    
    mcp.run(
        transport="sse",
        host=host,
        port=port
    )
