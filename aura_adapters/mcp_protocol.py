"""
===================================================================================
AURA ADAPTER: MODEL CONTEXT PROTOCOL (MCP) PROTOCOL & CONNECTORS
===================================================================================
Curated capabilities extracted from:
- modelcontextprotocol/python-sdk (Official JSON-RPC 2.0 Protocol Spec)
- github/github-mcp-server (GitHub Issues, PRs, Tree Schemas)
- microsoft/playwright-mcp (Browser Automation MCP Tool Declarations)
- punkpeye/awesome-mcp-servers (Community Discovery Catalog)
===================================================================================
"""
import json
import uuid
from typing import Dict, Any, List, Optional


class MCPSpecificationHandler:
    """Official Model Context Protocol (MCP) JSON-RPC 2.0 message parser and validator."""
    @staticmethod
    def create_request(method: str, params: Dict[str, Any], req_id: Optional[str] = None) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id or uuid.uuid4().hex[:8],
            "method": method,
            "params": params
        }

    @staticmethod
    def create_response(req_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }

    @staticmethod
    def create_tool_declaration(name: str, description: str, input_schema: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": name,
            "description": description,
            "inputSchema": input_schema
        }


class GitHubMCPConnector:
    """GitHub MCP Server tool definitions."""
    @staticmethod
    def get_tool_declarations() -> List[Dict[str, Any]]:
        return [
            MCPSpecificationHandler.create_tool_declaration(
                name="github_get_issue",
                description="Fetches an issue from a GitHub repository",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "issue_number": {"type": "integer"}
                    },
                    "required": ["owner", "repo", "issue_number"]
                }
            ),
            MCPSpecificationHandler.create_tool_declaration(
                name="github_create_pull_request",
                description="Creates a pull request with code changes",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "head": {"type": "string"},
                        "base": {"type": "string"}
                    },
                    "required": ["owner", "repo", "title", "head", "base"]
                }
            )
        ]


class PlaywrightMCPConnector:
    """Playwright MCP Server tool definitions."""
    @staticmethod
    def get_tool_declarations() -> List[Dict[str, Any]]:
        return [
            MCPSpecificationHandler.create_tool_declaration(
                name="browser_navigate",
                description="Navigates the headless browser to a specific URL",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"]
                }
            ),
            MCPSpecificationHandler.create_tool_declaration(
                name="browser_click",
                description="Clicks an element using CSS selector or coordinates",
                input_schema={
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "x": {"type": "number"},
                        "y": {"type": "number"}
                    }
                }
            ),
            MCPSpecificationHandler.create_tool_declaration(
                name="browser_screenshot",
                description="Takes a viewport or full-page screenshot",
                input_schema={
                    "type": "object",
                    "properties": {"full_page": {"type": "boolean", "default": False}}
                }
            )
        ]
