"""Apartments.com scraper."""

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


class ApartmentsScraper(BaseScraper):
    """Apartments.com scraper."""
    
    @property
    def actor_id(self) -> str:
        """Get Apify actor ID for Apartments.com.
        
        Returns:
            Actor ID
        """
        return "epctex/apartments-scraper"
    
    @property
    def source_name(self) -> str:
        """Get source name.
        
        Returns:
            Source name
        """
        return "apartments"
    
    def prepare_input(self) -> Dict[str, Any]:
        """Prepare input for the Apartments.com scraper.
        
        Returns:
            Actor input
        """
        # Parse location into city and state
        location_parts = self.search_criteria.location.split(",")
        city = location_parts[0].strip().replace(" ", "-").lower()
        state = ""
        if len(location_parts) > 1:
            state = location_parts[1].strip().lower()
        
        # Construct location for URL
        if state:
            location_url = f"{city}-{state}"
        else:
            location_url = city
        
        # Base URL
        base_url = f"https://www.apartments.com/{location_url}"
        
        # Start building search parameters
        search_params = {}
        
        # Bedrooms filter
        if self.search_criteria.min_bedrooms > 0 and self.search_criteria.max_bedrooms:
            if self.search_criteria.min_bedrooms == self.search_criteria.max_bedrooms:
                search_params["br"] = str(self.search_criteria.min_bedrooms)
            else:
                search_params["br-min"] = str(self.search_criteria.min_bedrooms)
                search_params["br-max"] = str(self.search_criteria.max_bedrooms)
        elif self.search_criteria.min_bedrooms > 0:
            search_params["br-min"] = str(self.search_criteria.min_bedrooms)
        elif self.search_criteria.max_bedrooms:
            search_params["br-max"] = str(self.search_criteria.max_bedrooms)
        
        # Price filter
        if self.search_criteria.min_price > 0:
            search_params["price-min"] = str(int(self.search_criteria.min_price))
        if self.search_criteria.max_price:
            search_params["price-max"] = str(int(self.search_criteria.max_price))
        
        # Property type - apartments.com primarily focuses on apartments, but can filter for types
        if self.search_criteria.property_type != "any" and self.search_criteria.property_type != "apartment":
            search_params["type"] = self.search_criteria.property_type
        
        return {
            "startUrls": [{"url": base_url}],
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
        """Transform an Apartments.com listing to a PropertyListing.
        
        Args:
            item: Apartments.com listing
            
        Returns:
            PropertyListing
        """
        # Parse price
        price_str = item.get("rent", "0")
        if isinstance(price_str, str):
            # Extract digits from price string
            price_match = re.search(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)', price_str)
            if price_match:
                price_clean = price_match.group(1).replace(",", "")
                price = float(price_clean)
            else:
                price = 0
        else:
            price = float(price_str) if price_str else 0
        
        # Parse address
        property_address = item.get("propertyAddress", {})
        address_line = property_address.get("addressLine", "")
        neighborhood = property_address.get("neighborhood", "")
        city = property_address.get("city", "")
        state = property_address.get("state", "")
        postal_code = property_address.get("postalCode", None)
        
        address = Address(
            street=address_line,
            city=city or neighborhood,  # Use neighborhood if city is missing
            state=state,
            zip_code=postal_code
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
        property_type = "apartment"  # Default for apartments.com
        if "condo" in item.get("title", "").lower() or "condo" in item.get("description", "").lower():
            property_type = "condo"
        elif "townhouse" in item.get("title", "").lower() or "townhouse" in item.get("description", "").lower():
            property_type = "townhouse"
        elif "house" in item.get("title", "").lower() and "townhouse" not in item.get("title", "").lower():
            property_type = "house"
        
        # Get URL
        url = item.get("url", "")
        
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
        amenities = []
        
        # Add apartment amenities
        apartment_amenities = item.get("apartmentAmenities", [])
        if isinstance(apartment_amenities, list):
            amenities.extend(apartment_amenities)
        
        # Add community amenities
        community_amenities = item.get("communityAmenities", [])
        if isinstance(community_amenities, list):
            amenities.extend(community_amenities)
        
        # Also use the base extract_amenities method to catch any missed ones
        amenities.extend(self.extract_amenities(item))
        
        # Remove duplicates while preserving order
        amenities = list(dict.fromkeys(amenities))
        
        # Generate a unique ID
        property_id = str(item.get("id", uuid.uuid4()))
        
        # Create features dictionary for additional data
        additional_features = {}
        for key, value in item.items():
            if key not in [
                "rent", "propertyAddress", "beds", "baths", "sqft", "url", "photos",
                "apartmentAmenities", "communityAmenities", "id", "title", "description",
            ]:
                additional_features[key] = value
        
        # Parse listing date if available
        listed_date = None
        date_str = item.get("dateAvailable", item.get("datePosted", None))
        if date_str and isinstance(date_str, str):
            try:
                # Try common date formats
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y"]:
                    try:
                        listed_date = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
            except Exception:
                pass
        
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
            source="apartments",
            amenities=amenities,
            images=images,
            listed_date=listed_date,
            features=additional_features
        ) 