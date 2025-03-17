"""Realtor.com scraper."""

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


class RealtorScraper(BaseScraper):
    """Realtor.com scraper."""
    
    @property
    def actor_id(self) -> str:
        """Get Apify actor ID for Realtor.com.
        
        Returns:
            Actor ID
        """
        return "epctex/realtor-scraper"
    
    @property
    def source_name(self) -> str:
        """Get source name.
        
        Returns:
            Source name
        """
        return "realtor"
    
    def prepare_input(self) -> Dict[str, Any]:
        """Prepare input for the Realtor.com scraper.
        
        Returns:
            Actor input
        """
        # Parse location into city and state
        location_parts = self.search_criteria.location.split(",")
        city = location_parts[0].strip().replace(" ", "-").lower()
        state = ""
        if len(location_parts) > 1:
            state = location_parts[1].strip().lower()
        
        # Property type mapping
        property_type_map = {
            "apartment": "apartments",
            "house": "single-family-home",
            "condo": "condos",
            "townhouse": "townhomes",
            "any": "any"
        }
        
        property_type = property_type_map.get(
            self.search_criteria.property_type, "any"
        )
        
        # Base search URL
        if self.search_criteria.search_type == "rent":
            base_url = "https://www.realtor.com/apartments"
        else:
            base_url = "https://www.realtor.com/realestateandhomes-search"
        
        # Construct location part of URL
        if state:
            location_url = f"{city}_{state}"
        else:
            location_url = city
        
        # Build search URL
        input_url = f"{base_url}/{location_url}"
        
        # Start building search parameters
        search_params = {}
        
        # Add property type
        if property_type != "any":
            search_params["prop"] = property_type
        
        # Add bedroom filter
        if self.search_criteria.min_bedrooms > 0:
            search_params["beds-lower"] = str(self.search_criteria.min_bedrooms)
        if self.search_criteria.max_bedrooms:
            search_params["beds-upper"] = str(self.search_criteria.max_bedrooms)
        
        # Add price filter
        if self.search_criteria.min_price > 0:
            search_params["price-lower"] = str(int(self.search_criteria.min_price))
        if self.search_criteria.max_price:
            search_params["price-upper"] = str(int(self.search_criteria.max_price))
        
        return {
            "startUrls": [{"url": input_url}],
            "searchParams": search_params,
            "maxItems": self.max_items,
            "extendOutputFunction": """async ({ data, item, customData, Apify }) => {
                return { ...item };
            }""",
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"]
            }
        }
    
    def transform_item(self, item: Dict[str, Any]) -> PropertyListing:
        """Transform a Realtor.com listing to a PropertyListing.
        
        Args:
            item: Realtor.com listing
            
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
            price = float(price_str) if price_str else 0
        
        # Get address components
        full_address = item.get("address", "")
        address_components = item.get("addressComponents", {})
        
        # Construct address
        street = address_components.get("streetName", "")
        if "streetNumber" in address_components:
            street = f"{address_components['streetNumber']} {street}"
            
        address = Address(
            street=street,
            city=address_components.get("city", ""),
            state=address_components.get("state", ""),
            zip_code=address_components.get("zipcode", None)
        )
        
        # Parse bedrooms
        bedrooms = 0
        beds = item.get("beds", 0)
        if isinstance(beds, str):
            bed_match = re.search(r'(\d+\.?\d*)', beds)
            bedrooms = float(bed_match.group(1)) if bed_match else 0
        else:
            bedrooms = float(beds) if beds else 0
        
        # Parse bathrooms
        bathrooms = None
        baths = item.get("baths", None)
        if baths:
            if isinstance(baths, str):
                bath_match = re.search(r'(\d+\.?\d*)', baths)
                bathrooms = float(bath_match.group(1)) if bath_match else None
            else:
                bathrooms = float(baths)
        
        # Parse square feet
        sqft = None
        sqft_str = item.get("sqft", None)
        if sqft_str:
            if isinstance(sqft_str, str):
                sqft_match = re.search(r'(\d+)', sqft_str.replace(',', ''))
                sqft = int(sqft_match.group(1)) if sqft_match else None
            else:
                sqft = int(sqft_str)
        
        # Determine property type
        property_type = item.get("propertyType", "").lower()
        if not property_type:
            property_subtype = item.get("propertySubType", "").lower()
            if property_subtype:
                property_type = property_subtype
            else:
                property_type = "unknown"
        
        # Get URL
        url = item.get("detailUrl", "")
        if not url.startswith("http"):
            url = f"https://www.realtor.com{url}"
        
        # Get images
        images = []
        photos = item.get("photos", [])
        if isinstance(photos, list):
            for photo in photos:
                if isinstance(photo, dict) and "url" in photo:
                    images.append(photo["url"])
                elif isinstance(photo, str) and photo.startswith("http"):
                    images.append(photo)
        
        # Extract amenities
        amenities = self.extract_amenities(item)
        
        # Check for specific features in the item data
        features = item.get("features", {})
        if features:
            for category, feature_list in features.items():
                if isinstance(feature_list, list):
                    amenities.extend(feature_list)
        
        # Generate a unique ID
        property_id = str(item.get("listingId", uuid.uuid4()))
        
        # Create features dictionary for additional data
        additional_features = {}
        for key, value in item.items():
            if key not in [
                "price", "address", "addressComponents", "beds", "baths", "sqft",
                "propertyType", "propertySubType", "detailUrl", "photos", "features",
                "listingId", "description", "amenities"
            ]:
                additional_features[key] = value
        
        return PropertyListing(
            id=property_id,
            title=item.get("title", "Property Listing"),
            description=item.get("description", None),
            price=price,
            address=address,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            square_feet=sqft,
            property_type=property_type,
            url=url,
            source="realtor",
            amenities=amenities,
            images=images,
            features=additional_features
        ) 