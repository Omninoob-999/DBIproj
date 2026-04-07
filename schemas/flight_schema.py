from pydantic import BaseModel, Field
from typing import List, Optional

class TripAddon(BaseModel):
    """Add-ons for a specific flight leg"""
    flight_route: str = Field(..., description="The specific route this applies to, e.g., 'Bangkok - Don Mueang to Chiang Mai'")
    seat: Optional[str] = Field(None, description="Seat number (e.g., '6E', '7D')")
    baggage: Optional[str] = Field(None, description="Baggage allowance (e.g., '7 kg Carry-on baggage')")
    meal: Optional[str] = Field(None, description="Meal preference if any")
    other_services: List[str] = Field(default_factory=list, description="Any other services or extras purchased")

class Guest(BaseModel):
    """Individual passenger details"""
    name: str = Field(..., description="Full name of the passenger")
    passenger_type: str = Field(..., description="Type of passenger: adult, child, infant")
    trip_addons: List[TripAddon] = Field(..., description="Add-ons and seat allocations for each flight leg")

class FlightSegment(BaseModel):
    """Individual flight leg details"""
    flight_number: str = Field(..., description="Flight number (e.g., FD 3433)")
    airline: str = Field(..., description="Airline name (e.g., AirAsia)")
    origin_airport: str = Field(..., description="Departure airport code (e.g., DMK)")
    destination_airport: str = Field(..., description="Arrival airport code (e.g., CNX)")
    origin_city: str = Field(..., description="Departure city (e.g., Bangkok)")
    destination_city: str = Field(..., description="Arrival city (e.g., Chiang Mai)")
    departure_time: str = Field(..., description="Departure time (e.g., 13:10)")
    arrival_time: str = Field(..., description="Arrival time (e.g., 14:25)")
    flight_date: str = Field(..., description="Date of the flight (e.g., Wed, Oct 08)")
    duration: str = Field(..., description="Flight duration (e.g., 1h 15m)")
    cabin_class: Optional[str] = Field(None, description="Cabin class (e.g., Economy, Economy Promo)")

class FlightBooking(BaseModel):
    """Complete flight booking information"""
    booking_number: str = Field(..., description="Booking reference or PNR (e.g., J8P8KS)")
    booking_date: str = Field(..., description="Date when booking was made (e.g., 02 Oct 2025)")
    flight_segments: List[FlightSegment] = Field(..., description="All flight legs in the itinerary (outbound and return)")
    guests: List[Guest] = Field(..., description="All passengers on this booking with their individual add-ons per flight")
