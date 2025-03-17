"""Property data models for Listing Sleuth."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime


class Address(BaseModel):
    """Model for property address."""
    
    street: Optional[str] = None
    city: str
    state: str
    zip_code: Optional[str] = None
    country: str = "United States"
    
    def __str__(self) -> str:
        """Return string representation of address."""
        parts = []
        if self.street:
            parts.append(self.street)
        parts.append(f"{self.city}, {self.state}")
        if self.zip_code:
            parts.append(self.zip_code)
        return ", ".join(parts)


class PropertyListing(BaseModel):
    """Model for property listing data."""
    
    id: str
    title: str
    description: Optional[str] = None
    price: float
    address: Address
    bedrooms: float
    bathrooms: Optional[float] = None
    square_feet: Optional[int] = None
    property_type: str
    url: HttpUrl
    source: str
    amenities: List[str] = Field(default_factory=list)
    images: List[HttpUrl] = Field(default_factory=list)
    listed_date: Optional[datetime] = None
    is_new: bool = False  # Flag for new listings since last search
    features: Dict[str, Any] = Field(default_factory=dict)  # Additional property features
    
    class Config:
        """Pydantic config."""
        
        extra = "ignore"


class SearchCriteria(BaseModel):
    """Model for search criteria."""
    
    location: str
    property_type: str = "any"
    min_bedrooms: int = 0
    max_bedrooms: Optional[int] = None
    min_price: float = 0
    max_price: Optional[float] = None
    amenities: List[str] = Field(default_factory=list)
    search_type: str = "rent"
    sources: List[str] = Field(default=["zillow", "realtor", "apartments"])
    llm_api_token: Optional[str] = None


class SearchResults(BaseModel):
    """Model for search results."""
    
    search_criteria: SearchCriteria
    results: List[PropertyListing] = Field(default_factory=list)
    total_results: int = 0
    new_results: int = 0
    search_date: datetime = Field(default_factory=datetime.now)
    sources_searched: List[str] = Field(default_factory=list) 