#!/usr/bin/env python3
"""
Avathon Client - Global client management for Avathon API.

Similar to Procore's approach - manages authentication and HTTP client
globally, avoiding the need for dependencies in ExecutionDependencies.
"""

import os
import logging
from typing import Optional, Dict, Any
import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Global client instance
_avathon_client: Optional['AvathonClient'] = None


class AvathonClient:
    """
    Global Avathon API client.
    Manages authentication and HTTP operations.
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 deployment: str = "sc-st-renewables-prod",
                 base_url: Optional[str] = None):
        """
        Initialize Avathon client.
        
        Args:
            api_key: Avathon API key (or from env AVATHON_API_KEY)
            deployment: Deployment environment (default: sc-mt-sandbox)
            base_url: Override full base URL if needed
        """
        self.api_key = api_key or os.getenv("AVATHON_API_KEY")
        if not self.api_key:
            raise ValueError("AVATHON_API_KEY environment variable or api_key parameter required")
        
        # Build base URL from server template
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = f"https://{deployment}.apm.sparkcognition.com/v2"
        
        # Create async HTTP client
        self.http = httpx.AsyncClient(
            headers={
                "x-api-key": self.api_key,
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        
        logger.info(f"Avathon client initialized for {self.base_url}")
    
    async def request(self, 
                     method: str, 
                     path: str,
                     params: Optional[Dict[str, Any]] = None,
                     json_body: Optional[Dict[str, Any]] = None,
                     headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """
        Make an API request.
        
        Args:
            method: HTTP method
            path: API path (can contain {placeholders})
            params: Query parameters
            json_body: JSON request body
            headers: Additional headers
            
        Returns:
            HTTP response
        """
        # Build full URL
        url = self.base_url + path
        
        # Prepare headers
        request_headers = {}
        if headers:
            request_headers.update(headers)
        
        # Make request
        response = await self.http.request(
            method=method,
            url=url,
            params=params,
            json=json_body,
            headers=request_headers
        )
        
        logger.debug(f"{method} {url} -> {response.status_code}")
        return response
    
    async def get(self, path: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> httpx.Response:
        """Convenience method for GET requests."""
        return await self.request("GET", path, params=params, **kwargs)
    
    async def post(self, path: str, json_body: Optional[Dict[str, Any]] = None, **kwargs) -> httpx.Response:
        """Convenience method for POST requests."""
        return await self.request("POST", path, json_body=json_body, **kwargs)
    
    async def put(self, path: str, json_body: Optional[Dict[str, Any]] = None, **kwargs) -> httpx.Response:
        """Convenience method for PUT requests."""
        return await self.request("PUT", path, json_body=json_body, **kwargs)
    
    async def delete(self, path: str, **kwargs) -> httpx.Response:
        """Convenience method for DELETE requests."""
        return await self.request("DELETE", path, **kwargs)
    
    async def close(self):
        """Close the HTTP client."""
        await self.http.aclose()


def get_avathon_client() -> AvathonClient:
    """
    Get the global Avathon client instance.
    Creates one if it doesn't exist.
    """
    global _avathon_client
    
    if _avathon_client is None:
        # Load environment variables
        load_dotenv()
        _avathon_client = AvathonClient()
    
    return _avathon_client


def set_avathon_client(client: AvathonClient):
    """Set the global Avathon client instance."""
    global _avathon_client
    _avathon_client = client


async def close_avathon_client():
    """Close the global client."""
    global _avathon_client
    if _avathon_client:
        await _avathon_client.close()
        _avathon_client = None