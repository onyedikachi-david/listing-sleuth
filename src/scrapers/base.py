"""Base scraper class for all real estate platform scrapers."""

import re
import json
import uuid
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from apify import Actor
from apify_client import ApifyClient
from pydantic import HttpUrl

from ..models.property import PropertyListing, Address, SearchCriteria


class BaseScraper(ABC):
    """Base scraper class that all platform-specific scrapers should inherit from."""
    
    def __init__(
        self,
        search_criteria: SearchCriteria,
        apify_client: Optional[ApifyClient] = None,
        max_items: int = 100
    ):
        """Initialize the scraper.
        
        Args:
            search_criteria: Search criteria
            apify_client: Apify client. If None, creates a new client
            max_items: Maximum number of items to scrape
        """
        self.search_criteria = search_criteria
        self.apify_client = apify_client or ApifyClient()
        self.max_items = max_items
        
    @property
    @abstractmethod
    def actor_id(self) -> str:
        """Apify actor ID for the scraper.
        
        Returns:
            Actor ID
        """
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the source.
        
        Returns:
            Source name
        """
        pass
    
    @abstractmethod
    def prepare_input(self) -> Dict[str, Any]:
        """Prepare input for the Apify actor.
        
        Returns:
            Actor input
        """
        pass
    
    @abstractmethod
    def transform_item(self, item: Dict[str, Any]) -> PropertyListing:
        """Transform a scraped item into a PropertyListing.
        
        Args:
            item: Scraped item
            
        Returns:
            PropertyListing
        """
        pass
    
    def parse_address(self, address_str: str) -> Address:
        """Parse address string into Address model.
        
        Args:
            address_str: Address string
            
        Returns:
            Address
        """
        # Default implementation with simple parsing
        # Subclasses can override for platform-specific parsing
        address_parts = address_str.split(",")
        
        if len(address_parts) >= 3:
            street = address_parts[0].strip()
            city = address_parts[1].strip()
            state_zip = address_parts[2].strip().split()
            state = state_zip[0].strip() if state_zip else ""
            zip_code = state_zip[1].strip() if len(state_zip) > 1 else None
        elif len(address_parts) == 2:
            street = None
            city = address_parts[0].strip()
            state_zip = address_parts[1].strip().split()
            state = state_zip[0].strip() if state_zip else ""
            zip_code = state_zip[1].strip() if len(state_zip) > 1 else None
        else:
            # If we can't parse the address properly, use a minimal approach
            street = None
            # Try to extract a known state abbreviation
            state_match = re.search(r'\b([A-Z]{2})\b', address_str)
            if state_match:
                state = state_match.group(1)
                # Assume the city is before the state
                city_match = re.search(r'([^,]+),\s*' + state, address_str)
                city = city_match.group(1) if city_match else address_str
            else:
                # If we can't extract a state, use the whole string as city
                city = address_str
                state = ""
            zip_code = None
        
        return Address(
            street=street,
            city=city,
            state=state,
            zip_code=zip_code
        )
    
    def extract_amenities(self, item: Dict[str, Any]) -> List[str]:
        """Extract amenities from a scraped item.
        
        Args:
            item: Scraped item
            
        Returns:
            List of amenities
        """
        # Default implementation that subclasses can override
        amenities = []
        
        # Look for amenities in features or amenities field
        if "amenities" in item and isinstance(item["amenities"], list):
            amenities.extend(item["amenities"])
        
        if "features" in item and isinstance(item["features"], list):
            amenities.extend(item["features"])
        
        # Look for amenities in description
        if "description" in item and isinstance(item["description"], str):
            # Common amenities to look for in descriptions
            common_amenities = [
                "parking", "garage", "gym", "fitness", "pool", "washer", "dryer", 
                "dishwasher", "air conditioning", "ac", "balcony", "patio", 
                "hardwood", "fireplace", "wheelchair", "elevator", "pet friendly"
            ]
            
            description = item["description"].lower()
            for amenity in common_amenities:
                if amenity in description and amenity not in amenities:
                    amenities.append(amenity)
        
        return amenities
    
    def scrape(self) -> List[PropertyListing]:
        """Scrape properties based on search criteria.
        
        Returns:
            List of property listings
        """
        Actor.log.info(f"Starting {self.source_name} scraper")
        
        # Prepare input for the Apify actor
        input_data = self.prepare_input()
        
        # Check if we're running in local mode for testing
        if os.environ.get("ACTOR_TEST_PAY_PER_EVENT") == "true" and not os.environ.get("APIFY_TOKEN"):
            Actor.log.info(f"Running in local test mode, using mock data for {self.source_name}")
            return self.get_mock_listings()
        
        Actor.log.info(f"Running Apify actor {self.actor_id} with input: {input_data}")
        
        try:
            # Run the actor
            run = self.apify_client.actor(self.actor_id).call(
                run_input=input_data,
                build="latest"
            )
            
            # Get the dataset
            dataset_id = run["defaultDatasetId"]
            items = self.apify_client.dataset(dataset_id).list_items(limit=self.max_items).items
            
            Actor.log.info(f"Scraped {len(items)} items from {self.source_name}")
            
            # Transform items to PropertyListings
            listings = []
            for item in items:
                try:
                    listing = self.transform_item(item)
                    listings.append(listing)
                except Exception as e:
                    Actor.log.exception(f"Error transforming item: {e}")
                    continue
            
            Actor.log.info(f"Transformed {len(listings)} listings from {self.source_name}")
            
            return listings
        except Exception as e:
            Actor.log.error(f"Error scraping {self.source_name}: {e}")
            return self.get_mock_listings()
    
    def get_mock_listings(self) -> List[PropertyListing]:
        """Get mock listings for local testing.
        
        Returns:
            List of mock property listings
        """
        Actor.log.info(f"Generating mock data for {self.source_name}")
        
        # Create 5 mock listings
        mock_listings = []
        
        for i in range(1, 6):
            mock_listings.append(
                PropertyListing(
                    id=f"{self.source_name}_mock_{i}",
                    title=f"Mock {self.source_name} Listing {i}",
                    description=f"This is a mock listing for testing purposes. In {self.search_criteria.location} with {self.search_criteria.min_bedrooms} bedrooms.",
                    url=f"https://example.com/{self.source_name}/mock-listing-{i}",
                    price=float(self.search_criteria.min_price or 1000) + (i * 200),
                    bedrooms=self.search_criteria.min_bedrooms + (i % 2),
                    bathrooms=self.search_criteria.min_bedrooms / 2 + (i % 2),
                    address=Address(
                        street=f"{100 + i} Main St",
                        city=self.search_criteria.location.split(",")[0].strip(),
                        state=self.search_criteria.location.split(",")[-1].strip(),
                        zip_code="12345"
                    ),
                    property_type=self.search_criteria.property_type,
                    source=self.source_name,
                    amenities=self.search_criteria.amenities + ["parking", "air conditioning"],
                    listed_date=datetime.now(),
                    is_new=True
                )
            )
        
        Actor.log.info(f"Generated {len(mock_listings)} mock listings for {self.source_name}")
        return mock_listings 