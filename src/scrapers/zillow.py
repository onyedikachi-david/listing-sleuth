"""Zillow scraper."""

import re
import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import HttpUrl

from apify import Actor
from apify_client import ApifyClient

from .base import BaseScraper
from ..models.property import PropertyListing, Address, SearchCriteria


class ZillowScraper(BaseScraper):
    """Zillow scraper."""
    
    @property
    def actor_id(self) -> str:
        """Get Apify actor ID for Zillow.
        
        Returns:
            Actor ID
        """
        return "maxcopell/zillow-detail-scraper"
    
    @property
    def source_name(self) -> str:
        """Get source name.
        
        Returns:
            Source name
        """
        return "zillow"
    
    def prepare_input(self) -> Dict[str, Any]:
        """Prepare input for the Zillow scraper.
        
        Returns:
            Actor input
        """
        location = self.search_criteria.location.replace(", ", ",").replace(" ", "-").lower()
        
        # Property type mapping
        property_type_map = {
            "apartment": "apartment",
            "house": "house",
            "condo": "condo",
            "townhouse": "townhome",
            "any": ""
        }
        
        property_type = property_type_map.get(
            self.search_criteria.property_type, ""
        )
        
        # Build the URL
        if self.search_criteria.search_type == "rent":
            base_url = f"https://www.zillow.com/homes/for_rent/{location}"
        else:
            base_url = f"https://www.zillow.com/homes/{location}"
        
        # Add filters based on search criteria
        filters = []
        
        # Price filter
        if self.search_criteria.min_price > 0 or self.search_criteria.max_price:
            price_filter = "price"
            if self.search_criteria.min_price > 0:
                price_filter += f"_gte-{int(self.search_criteria.min_price)}"
            if self.search_criteria.max_price:
                price_filter += f"_lte-{int(self.search_criteria.max_price)}"
            filters.append(price_filter)
        
        # Bedroom filter
        if self.search_criteria.min_bedrooms > 0 or self.search_criteria.max_bedrooms:
            if self.search_criteria.min_bedrooms == self.search_criteria.max_bedrooms:
                filters.append(f"{self.search_criteria.min_bedrooms}-_beds")
            else:
                bedroom_filter = "beds"
                if self.search_criteria.min_bedrooms > 0:
                    bedroom_filter += f"_gte-{self.search_criteria.min_bedrooms}"
                if self.search_criteria.max_bedrooms:
                    bedroom_filter += f"_lte-{self.search_criteria.max_bedrooms}"
                filters.append(bedroom_filter)
        
        # Property type filter
        if property_type:
            filters.append(f"type-{property_type}")
        
        # Assemble the URL with filters
        if filters:
            filter_string = "/".join(filters)
            url = f"{base_url}/{filter_string}"
        else:
            url = base_url
        
        return {
            "startUrls": [{"url": url}],
            "maxPages": 10,
            "includeRental": self.search_criteria.search_type == "rent",
            "includeSale": self.search_criteria.search_type == "buy",
            "includeAuction": False,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"]
            }
        }
    
    def transform_item(self, item: Dict[str, Any]) -> PropertyListing:
        """Transform a Zillow listing to a PropertyListing.
        
        Args:
            item: Zillow listing
            
        Returns:
            PropertyListing
        """
        # Parse price
        price_str = item.get("price", "0")
        if isinstance(price_str, str):
            # Remove currency symbols and commas
            price_str = re.sub(r'[^\d.]', '', price_str)
            price = float(price_str) if price_str else 0
        else:
            price = float(price_str)
        
        # Parse address
        address_str = item.get("address", "")
        address = self.parse_address(address_str)
        
        # Parse bedrooms
        bedrooms_str = item.get("bedrooms", "0")
        if isinstance(bedrooms_str, str):
            bedroom_match = re.search(r'(\d+\.?\d*)', bedrooms_str)
            bedrooms = float(bedroom_match.group(1)) if bedroom_match else 0
        else:
            bedrooms = float(bedrooms_str) if bedrooms_str else 0
        
        # Parse bathrooms
        bathrooms_str = item.get("bathrooms", None)
        if bathrooms_str:
            if isinstance(bathrooms_str, str):
                bathroom_match = re.search(r'(\d+\.?\d*)', bathrooms_str)
                bathrooms = float(bathroom_match.group(1)) if bathroom_match else None
            else:
                bathrooms = float(bathrooms_str)
        else:
            bathrooms = None
        
        # Parse square feet
        sqft_str = item.get("livingArea", None)
        if sqft_str:
            if isinstance(sqft_str, str):
                # Remove non-digit characters
                sqft_match = re.search(r'(\d+)', sqft_str.replace(',', ''))
                sqft = int(sqft_match.group(1)) if sqft_match else None
            else:
                sqft = int(sqft_str)
        else:
            sqft = None
        
        # Extract amenities
        amenities = self.extract_amenities(item)
        
        # Get property type
        property_type = item.get("homeType", "").lower()
        if not property_type:
            # Try to infer from description or facts
            if "apartment" in item.get("description", "").lower():
                property_type = "apartment"
            elif "condo" in item.get("description", "").lower():
                property_type = "condo"
            elif "house" in item.get("description", "").lower():
                property_type = "house"
            elif "townhouse" in item.get("description", "").lower() or "town house" in item.get("description", "").lower():
                property_type = "townhouse"
            else:
                property_type = "unknown"
        
        # Get listing URL
        url = item.get("url", "")
        if not url.startswith("http"):
            url = f"https://www.zillow.com{url}"
        
        # Get images
        images = []
        if "images" in item and isinstance(item["images"], list):
            for img in item["images"]:
                if isinstance(img, str) and img.startswith("http"):
                    images.append(img)
        
        # Generate a unique ID
        property_id = str(item.get("zpid", uuid.uuid4()))
        
        # Extract any additional features
        features = {}
        for key, value in item.items():
            if key not in [
                "price", "address", "bedrooms", "bathrooms", "livingArea", 
                "homeType", "description", "url", "images", "zpid", "amenities"
            ]:
                features[key] = value
        
        return PropertyListing(
            id=property_id,
            title=item.get("streetAddress", "Property Listing"),
            description=item.get("description", None),
            price=price,
            address=address,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            square_feet=sqft,
            property_type=property_type,
            url=url,
            source="zillow",
            amenities=amenities,
            images=images,
            features=features
        ) 