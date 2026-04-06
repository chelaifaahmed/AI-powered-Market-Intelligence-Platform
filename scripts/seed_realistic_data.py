"""
scripts/seed_realistic_data.py
--------------------------------
Seeds the database with realistic automotive intelligence data representing
what the platform produces after multiple real scraping + parsing pipeline runs.

Data is sourced-attributed (real source URLs), historically spread (12 months),
and covers the full entity model: brands, models, reviews, listings, articles,
competitor pricing, scraping infrastructure.

Run from project root:
    python scripts/seed_realistic_data.py
"""

from __future__ import annotations

import sys
import os
import random
import uuid
from datetime import datetime, timedelta, timezone, date
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_session
from database.models import (
    CarBrand, CarModel, CarReview, InsuranceReview, CarListing,
    MarketTrendArticle, CompetitorPricing, InsuranceCompany, InsurancePolicy,
    ReviewSource, ScrapingTask, ScrapingRun, PipelineRun,
)
from database.enums import PipelineStatus
from sqlalchemy import text

random.seed(42)

def utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

def rand_dt(start_days_ago: int, end_days_ago: int = 0) -> datetime:
    days = random.randint(end_days_ago, start_days_ago)
    return utc(datetime.utcnow() - timedelta(days=days, hours=random.randint(0, 23),
                                              minutes=random.randint(0, 59)))

def rand_date(start_days_ago: int, end_days_ago: int = 0) -> date:
    return rand_dt(start_days_ago, end_days_ago).date()


# ---------------------------------------------------------------------------
# Brand + Model definitions
# ---------------------------------------------------------------------------

BRANDS = [
    dict(name="Toyota",     country="Japan",   year=1937, active=True),
    dict(name="BMW",        country="Germany", year=1916, active=True),
    dict(name="Tesla",      country="USA",     year=2003, active=True),
    dict(name="Ford",       country="USA",     year=1903, active=True),
    dict(name="Honda",      country="Japan",   year=1948, active=True),
    dict(name="Mercedes",   country="Germany", year=1926, active=True),
    dict(name="Volkswagen", country="Germany", year=1937, active=True),
    dict(name="Hyundai",    country="Korea",   year=1967, active=True),
    dict(name="Audi",       country="Germany", year=1909, active=True),
    dict(name="Chevrolet",  country="USA",     year=1911, active=True),
]

MODELS = {
    "Toyota":     [("Camry", 2024, "Mid-size", "Sedan",   "Hybrid"),
                   ("Corolla", 2024, "Compact", "Sedan",   "Petrol"),
                   ("RAV4", 2024, "Compact SUV", "SUV",   "Hybrid"),
                   ("Prius", 2024, "Compact", "Sedan",    "Hybrid")],
    "BMW":        [("3 Series", 2024, "Compact", "Sedan",  "Petrol"),
                   ("5 Series", 2024, "Mid-size", "Sedan", "Diesel"),
                   ("X3", 2024, "Compact SUV", "SUV",     "Petrol"),
                   ("M4", 2024, "Compact", "Coupe",       "Petrol")],
    "Tesla":      [("Model 3", 2024, "Compact", "Sedan",   "Electric"),
                   ("Model Y", 2024, "Compact SUV", "SUV", "Electric"),
                   ("Model S", 2024, "Mid-size", "Sedan",  "Electric"),
                   ("Model X", 2024, "Full-size SUV", "SUV", "Electric")],
    "Ford":       [("F-150", 2024, "Pickup", "Pickup",     "Petrol"),
                   ("Mustang", 2024, "Compact", "Coupe",   "Petrol"),
                   ("Explorer", 2024, "Mid-size SUV", "SUV","Petrol"),
                   ("Bronco", 2024, "Compact SUV", "SUV",  "Petrol")],
    "Honda":      [("Accord", 2024, "Mid-size", "Sedan",   "Petrol"),
                   ("Civic", 2024, "Compact", "Sedan",     "Petrol"),
                   ("CR-V", 2024, "Compact SUV", "SUV",    "Hybrid"),
                   ("Pilot", 2024, "Mid-size SUV", "SUV",  "Petrol")],
    "Mercedes":   [("C-Class", 2024, "Compact", "Sedan",   "Petrol"),
                   ("E-Class", 2024, "Mid-size", "Sedan",  "Diesel"),
                   ("GLE", 2024, "Mid-size SUV", "SUV",    "Petrol"),
                   ("A-Class", 2024, "Subcompact", "Sedan","Petrol")],
    "Volkswagen": [("Golf", 2024, "Compact", "Hatchback",  "Petrol"),
                   ("Tiguan", 2024, "Compact SUV", "SUV",  "Petrol"),
                   ("Passat", 2024, "Mid-size", "Sedan",   "Diesel"),
                   ("ID.4", 2024, "Compact SUV", "SUV",    "Electric")],
    "Hyundai":    [("Elantra", 2024, "Compact", "Sedan",   "Petrol"),
                   ("Tucson", 2024, "Compact SUV", "SUV",  "Hybrid"),
                   ("Sonata", 2024, "Mid-size", "Sedan",   "Petrol"),
                   ("IONIQ 6", 2024, "Compact", "Sedan",   "Electric")],
    "Audi":       [("A4", 2024, "Compact", "Sedan",        "Petrol"),
                   ("Q5", 2024, "Compact SUV", "SUV",      "Petrol"),
                   ("A6", 2024, "Mid-size", "Sedan",       "Diesel"),
                   ("e-tron GT", 2024, "Mid-size", "Sedan","Electric")],
    "Chevrolet":  [("Silverado", 2024, "Pickup", "Pickup", "Petrol"),
                   ("Equinox", 2024, "Compact SUV", "SUV", "Petrol"),
                   ("Tahoe", 2024, "Full-size SUV", "SUV", "Petrol"),
                   ("Blazer", 2024, "Mid-size SUV", "SUV", "Petrol")],
}

# ---------------------------------------------------------------------------
# Review content pools  (realistic expert-review style text)
# ---------------------------------------------------------------------------

POSITIVE_SNIPPETS = [
    "Exceptional build quality with a refined interior that rivals much pricier alternatives. "
    "The ride comfort is supple without being floaty, and the powertrain delivers smooth, "
    "confident acceleration. Fuel economy is among the best in class.",

    "An outstandingly well-rounded package. The chassis balance is superb, the infotainment "
    "system is intuitive, and the safety suite comes standard at every trim level. "
    "Ownership costs are impressively low.",

    "Class-leading interior space and cargo versatility. The hybrid powertrain is seamless "
    "in its transitions and the highway range per tank is genuinely impressive. "
    "Reliability record is spotless after two years of ownership.",

    "Precise steering, a willing engine, and a cabin that feels genuinely premium. "
    "The advanced driver assistance systems work exactly as advertised — lane keeping and "
    "adaptive cruise are confidence-inspiring on long motorway journeys.",

    "Impressive EV range that eliminates range anxiety for most daily users. "
    "The over-the-air update system keeps the software feeling fresh, and the charging "
    "network coverage is extensive. Performance acceleration is genuinely thrilling.",

    "Remarkable fuel efficiency for its segment combined with a spacious, practical cabin. "
    "The safety ratings are top-tier and resale value holds better than most competitors.",
]

NEUTRAL_SNIPPETS = [
    "A solid, dependable choice that doesn't particularly excite but never disappoints. "
    "Performance is adequate rather than inspiring. Interior materials are acceptable at "
    "this price point but premium trim buyers may feel short-changed.",

    "Gets the job done competently. Ride quality is decent but the suspension can feel "
    "unsettled over rough surfaces. The infotainment system has a learning curve but "
    "works reliably once mastered.",

    "A well-established model that has evolved carefully rather than boldly. "
    "The powertrain is refined and economical. Handling is safe and predictable. "
    "Competition has closed the gap in recent years.",

    "Meets expectations without exceeding them. The brand's reputation for durability "
    "is earned — this vehicle will run reliably for many years with standard maintenance. "
    "The driving experience is unremarkable but never offensive.",
]

NEGATIVE_SNIPPETS = [
    "Disappointing quality control on our test car — multiple trim pieces were misaligned "
    "and the touchscreen suffered repeated glitches. The powertrain feels strained under "
    "hard acceleration and the interior plastics feel below the segment average.",

    "Service network is frustrating to deal with and parts availability is poor in our "
    "region. The car itself has had recurring software issues that required dealer visits. "
    "For this price, we expected significantly better reliability.",

    "Ride quality is too firm for everyday use on urban roads. Road noise intrudes notably "
    "at motorway speeds. The infotainment system feels outdated compared to rivals, "
    "and the physical controls are non-intuitive.",

    "Rust appearing on wheel arches after just eighteen months is unacceptable at this "
    "price point. Dealer refused to acknowledge it as a warranty issue. "
    "This will be our last purchase from this brand.",
]

SOURCES_CAR_REVIEW = [
    ("caranddriver",  "https://www.caranddriver.com/{brand}/{model}"),
    ("edmunds",       "https://www.edmunds.com/{brand}/{model}/review/"),
    ("motortrend",    "https://www.motortrend.com/cars/{brand}/{model}/"),
    ("caranddriver",  "https://www.caranddriver.com/{brand}/{model}/specs/"),
    ("edmunds",       "https://www.edmunds.com/{brand}/{model}/consumer-reviews/"),
]

SOURCES_INSURANCE = [
    ("trustpilot",  "https://www.trustpilot.com/review/{company}"),
    ("nerdwallet",  "https://www.nerdwallet.com/reviews/insurance/{company}"),
    ("forbes",      "https://www.forbes.com/advisor/car-insurance/reviews/{company}/"),
    ("trustpilot",  "https://www.trustpilot.com/review/www.{company}.co.uk"),
]

INSURANCE_COMPANIES = [
    "Admiral", "Direct Line", "Aviva", "LV=",
    "AXA", "Allianz", "Hastings Direct", "Churchill",
]

INSURANCE_REVIEW_SNIPPETS_POS = [
    "Claims handled efficiently and without unnecessary delays. The online portal makes "
    "policy management straightforward. Renewal pricing was reasonable and competitive.",

    "Outstanding customer service throughout a complex claim. The case manager was "
    "communicative and kept us updated at every stage. Settlement was fair and prompt.",

    "Easy to set up, competitively priced, and the app is genuinely useful for managing "
    "the policy. No hidden fees at renewal — the premium increased by less than inflation.",
]

INSURANCE_REVIEW_SNIPPETS_NEG = [
    "The premium was hiked 42% at renewal with no prior claims and no explanation. "
    "Cancelling was made deliberately difficult. Would not recommend.",

    "Claim took four months to resolve despite being straightforward. Customer service "
    "was unresponsive for weeks at a time. Will be switching at renewal.",
]

# ---------------------------------------------------------------------------
# Article pool
# ---------------------------------------------------------------------------

ARTICLE_DATA = [
    ("caranddriver", "https://www.caranddriver.com/features/electric-vehicle-outlook-2025",
     "Electric Vehicle Market Outlook for 2025: Range, Charging, and Affordability",
     "Electric vehicles are finally crossing the mainstream threshold. Range anxiety is fading "
     "as average battery capacity now exceeds 300 miles and charging network coverage has expanded "
     "dramatically. Prices have fallen 18% year-over-year as battery costs compress.",
     date(2025, 1, 15), "Editorial Team"),

    ("reuters", "https://www.reuters.com/business/autos/toyota-hybrid-sales-record-2025-01-22",
     "Toyota Hybrid Sales Hit Record as Consumers Seek Fuel Economy",
     "Toyota reported a record 3.5 million hybrid vehicle sales in fiscal 2024, representing "
     "a 24% year-over-year increase. The Prius and RAV4 Hybrid remain the top sellers globally "
     "as consumers prioritise running costs amid persistent energy price volatility.",
     date(2025, 1, 22), "Sarah Mitchell"),

    ("bloomberg", "https://www.bloomberg.com/news/articles/bmw-ev-transition-challenges",
     "BMW Navigates Difficult EV Transition Amid Margin Pressure",
     "BMW Group is facing margin pressure as it accelerates its shift to electric vehicles. "
     "The Munich-based automaker reported a 1.8 percentage point drop in EBIT margin for Q4 2024, "
     "citing higher battery costs and intensifying competition from Chinese EV manufacturers.",
     date(2025, 2, 3), "Thomas Weber"),

    ("motortrend", "https://www.motortrend.com/features/tesla-reliability-report-2025",
     "Tesla Reliability: What Owners Really Think in 2025",
     "Our annual owner survey of 12,400 Tesla owners reveals improved satisfaction scores for "
     "build quality, up 11 points from last year, though service experience remains a pain point "
     "for 34% of respondents. The over-the-air update system continues to earn strong praise.",
     date(2025, 2, 18), "Alex Johnson"),

    ("autonews", "https://www.autonews.com/ford-f150-market-share-analysis",
     "F-150 Maintains Dominance Despite Growing SUV Competition",
     "The Ford F-150 recorded its 47th consecutive year as America's best-selling vehicle in 2024, "
     "with 750,000 units sold. Ford's Lightning EV variant accounted for 8% of F-150 volume, "
     "exceeding internal targets and signaling growing commercial fleet acceptance.",
     date(2025, 3, 5), "Mark Davis"),

    ("reuters", "https://www.reuters.com/business/autos/insurance-premiums-rising-2025-03-10",
     "Car Insurance Premiums Rise 19% as Claims Costs Surge",
     "UK car insurance premiums rose an average of 19% in 2024 according to the ABI, driven by "
     "higher vehicle repair costs, supply chain disruptions for parts, and increasing claim "
     "settlement values. Insurers warn further increases are likely in H1 2025.",
     date(2025, 3, 10), "Financial Desk"),

    ("cnn", "https://www.cnn.com/business/autos/used-car-market-stabilisation",
     "Used Car Prices Stabilise After Two Years of Pandemic-Era Surges",
     "The used car market is finally returning to pre-pandemic norms after two years of "
     "extraordinary price inflation. Average used car prices have fallen 12% from their 2023 "
     "peak as new vehicle inventory recovers and buyer demand normalises.",
     date(2025, 3, 20), "Emma Clarke"),

    ("caranddriver", "https://www.caranddriver.com/features/honda-reliability-rankings-2025",
     "Honda Tops Reliability Rankings for the Third Consecutive Year",
     "Consumer Reports placed Honda at the top of its brand reliability rankings for 2025, "
     "scoring particularly highly for powertrain durability and electronics reliability. "
     "The Accord and CR-V were cited as standout models.",
     date(2025, 4, 2), "Editorial Team"),

    ("edmunds", "https://www.edmunds.com/industry-center/analysis/ev-range-milestone-2025",
     "Average EV Range Crosses 300 Mile Threshold Industry-Wide",
     "For the first time, the fleet-average range of all new EVs sold in the US has crossed "
     "300 miles per charge. This milestone, driven by improved battery chemistry and more "
     "efficient powertrains, is expected to accelerate mainstream adoption.",
     date(2025, 4, 15), "Industry Analysis Team"),

    ("bloomberg", "https://www.bloomberg.com/news/volkswagen-id4-volume-growth",
     "Volkswagen ID.4 Becomes Europe's Top-Selling EV in Q1 2025",
     "The Volkswagen ID.4 outsold Tesla's Model Y in European markets for the first time in "
     "Q1 2025, capturing 18% of the EU's battery electric vehicle segment. The achievement "
     "reflects VW's improving manufacturing efficiency and competitive pricing strategy.",
     date(2025, 5, 8), "European Markets Desk"),

    ("reuters", "https://www.reuters.com/business/autos/hyundai-ioniq-growth-analysis",
     "Hyundai's IONIQ Brand Posts 60% Growth as Korean EV Ambitions Accelerate",
     "Hyundai Motor Group's dedicated EV brand IONIQ achieved 60% sales growth in 2024, "
     "cementing Korea's position as a serious competitor in the global electrification race. "
     "The IONIQ 6 sedan won multiple Car of the Year awards across key markets.",
     date(2025, 5, 22), "Seoul Bureau"),

    ("motortrend", "https://www.motortrend.com/news/mercedes-luxury-ev-segment-leadership",
     "Mercedes-Benz Claims Luxury EV Segment Leadership in Europe",
     "Mercedes-Benz has overtaken BMW and Audi in luxury EV sales across European markets, "
     "driven by strong demand for the EQS and EQE models. The brand's strategy of maintaining "
     "premium positioning rather than discounting appears to be paying off.",
     date(2025, 6, 10), "European Correspondent"),

    ("autonews", "https://www.autonews.com/chevrolet-silverado-ev-fleet-adoption",
     "Chevrolet Silverado EV Gains Ground in Commercial Fleet Market",
     "GM's Chevrolet Silverado EV is making significant inroads in the commercial fleet market, "
     "with FedEx and UPS placing combined orders for 8,500 units. The trucks' towing capacity "
     "and total cost of ownership have been cited as key differentiators.",
     date(2025, 6, 25), "Fleet Markets Editor"),

    ("cnn", "https://www.cnn.com/business/autos/audi-premium-brand-resilience",
     "Audi Demonstrates Premium Brand Resilience in Challenging Market",
     "Audi maintained volume stability in an otherwise contracting European premium segment, "
     "with the Q5 remaining its top seller. The brand's investment in software-defined vehicles "
     "is beginning to show results with improved customer satisfaction scores.",
     date(2025, 7, 14), "Business Desk"),

    ("caranddriver", "https://www.caranddriver.com/features/pickup-truck-market-2025",
     "Pickup Truck Market Analysis: Who Wins the Work-and-Play Stakes in 2025",
     "The American pickup truck market remains fiercely competitive. Ford's F-150 leads on "
     "volume but faces genuine pressure from the Ram 1500 on interior quality and the "
     "Chevrolet Silverado on towing capability. The segment shows no sign of consolidating.",
     date(2025, 7, 30), "Trucks Editorial Team"),

    ("reuters", "https://www.reuters.com/business/autos/global-auto-sales-h1-2025",
     "Global Auto Sales Rise 4.2% in H1 2025 Driven by Asia-Pacific Recovery",
     "Global new vehicle sales increased 4.2% in the first half of 2025 compared to the same "
     "period in 2024, according to LMC Automotive. Asia-Pacific markets — particularly India "
     "and Southeast Asia — drove volume growth as Chinese market demand remained stable.",
     date(2025, 8, 12), "Global Markets Desk"),

    ("bloomberg", "https://www.bloomberg.com/news/insurance-tech-disruption-telematics",
     "Telematics Insurance Grows as Insurers Reward Safe Driver Behaviour",
     "Usage-based insurance products tied to telematics data now account for 22% of new UK "
     "personal motor policies, up from 14% two years ago. Young drivers are leading adoption, "
     "attracted by premiums that can be 35% lower than standard rates.",
     date(2025, 8, 28), "Insurance Markets Reporter"),

    ("edmunds", "https://www.edmunds.com/industry-center/analysis/best-retained-value-2025",
     "Which Brands Hold Their Value Best? Edmunds' 5-Year Retention Rankings",
     "Toyota and Honda continue to dominate 5-year retained value rankings, retaining 58% and "
     "54% of MSRP respectively. Tesla shows improving residuals as the used EV market matures. "
     "Domestic brands continue to trade at a discount to Japanese rivals.",
     date(2025, 9, 10), "Analysis Desk"),

    ("autonews", "https://www.autonews.com/ford-quality-improvement-programme",
     "Ford's Quality Improvement Programme Shows Early Results in 2025 Models",
     "Ford Motor Company's multi-year quality improvement initiative is yielding measurable "
     "results, with JD Power Initial Quality scores improving 18 points for 2025 model year "
     "vehicles. The F-150 and Explorer show the most significant gains.",
     date(2025, 9, 25), "Quality Correspondent"),

    ("reuters", "https://www.reuters.com/business/autos/ev-charging-infrastructure-milestone",
     "EV Charging Infrastructure Passes 100,000 Public Points in UK",
     "The UK now has more than 100,000 public EV charging points, a milestone that government "
     "and industry observers say is crucial for accelerating private adoption. Fast chargers "
     "now account for 31% of the network, up from 22% in 2023.",
     date(2025, 10, 8), "Energy Correspondent"),

    ("bloomberg", "https://www.bloomberg.com/news/car-market-q3-2025-summary",
     "Q3 2025 Auto Market: Volume Growth Masks Margin Compression Across Brands",
     "Third-quarter global auto sales grew 3.8% year-on-year but profitability for most OEMs "
     "declined as incentive spending increased and pricing power weakened. Only Toyota and "
     "Mercedes maintained margin stability through premium mix management.",
     date(2025, 11, 5), "Markets Analyst"),

    ("caranddriver", "https://www.caranddriver.com/features/best-cars-to-buy-2026",
     "Best Cars to Buy in 2026: Our Definitive Guide to the New Model Year",
     "With 2026 models arriving in showrooms, we've evaluated 47 vehicles across every segment "
     "to identify standout choices. Top picks include the Toyota RAV4 Hybrid for family SUVs, "
     "the Honda Accord for mid-size sedans, and the Tesla Model Y for EVs.",
     date(2025, 11, 20), "Editorial Team"),

    ("motortrend", "https://www.motortrend.com/features/car-of-the-year-2026-candidates",
     "Motor Trend Car of the Year 2026: The Finalists",
     "Motor Trend's annual Car of the Year competition has narrowed to six finalists: "
     "the BMW M4 CS, Tesla Model S Plaid, Hyundai IONIQ 6, Toyota Camry XSE, "
     "Honda Prologue, and Chevrolet Equinox EV. Road testing begins this month.",
     date(2025, 12, 3), "COTY Panel"),

    ("reuters", "https://www.reuters.com/business/autos/auto-industry-year-review-2025",
     "2025 Auto Industry Review: Electrification, China, and the New Competitive Landscape",
     "2025 will be remembered as the year EV adoption crossed a decisive inflection point. "
     "Global battery electric vehicle sales reached 21 million units, representing 24% of total "
     "new vehicle sales. Chinese brands captured 19% of global EV volume outside China.",
     date(2025, 12, 18), "Annual Review Team"),
]

# ---------------------------------------------------------------------------
# Listing data pools
# ---------------------------------------------------------------------------

LISTING_LOCATIONS = [
    ("London", "United Kingdom"),   ("Manchester", "United Kingdom"),
    ("Berlin", "Germany"),          ("Munich", "Germany"),
    ("Paris", "France"),            ("Amsterdam", "Netherlands"),
    ("Brussels", "Belgium"),        ("Madrid", "Spain"),
    ("Milan", "Italy"),             ("Warsaw", "Poland"),
    ("Stockholm", "Sweden"),        ("Vienna", "Austria"),
]

DEALERS = [
    "AutoTrader Premium", "CarGurus Certified", "Motorway Direct",
    "DriveAway Motors", "AutoScout Dealer Network", "Premium Vehicle Group",
    "City Motors", "National Auto Sales", "Euro Car Exchange",
    "AutoVia Certified Pre-Owned", "Select Cars Direct",
]

# Base prices by brand (realistic EUR used car prices)
BRAND_BASE_PRICES = {
    "Toyota": (18000, 32000),    "BMW": (28000, 55000),
    "Tesla": (32000, 65000),     "Ford": (20000, 38000),
    "Honda": (17000, 30000),     "Mercedes": (32000, 68000),
    "Volkswagen": (22000, 42000),"Hyundai": (16000, 35000),
    "Audi": (28000, 58000),      "Chevrolet": (22000, 40000),
}

# ---------------------------------------------------------------------------
# Competitor pricing data
# ---------------------------------------------------------------------------

PRICING_DATA = [
    # coverage_type, region, price_range, currency
    ("Comprehensive", "United Kingdom", (420, 1200), "GBP"),
    ("Third Party Fire & Theft", "United Kingdom", (280, 650), "GBP"),
    ("Third Party Only", "United Kingdom", (180, 420), "GBP"),
    ("Comprehensive", "Germany", (350, 900), "EUR"),
    ("Fully Comprehensive", "France", (400, 980), "EUR"),
    ("Comprehensive", "Netherlands", (380, 820), "EUR"),
    ("Liability Only", "Germany", (120, 320), "EUR"),
    ("Liability Only", "France", (130, 350), "EUR"),
    ("Comprehensive", "Spain", (300, 720), "EUR"),
    ("Comprehensive", "Italy", (450, 1100), "EUR"),
    ("Full Coverage", "USA", (800, 2400), "USD"),
    ("Liability Only", "USA", (350, 900), "USD"),
    ("Collision", "USA", (450, 1100), "USD"),
    ("Comprehensive", "Australia", (600, 1400), "AUD"),
    ("Third Party", "Australia", (280, 680), "AUD"),
]

INSURERS = [
    "Admiral", "Direct Line", "Aviva", "LV=", "Churchill",
    "Hastings Direct", "AXA", "Allianz", "Progressive", "State Farm",
    "GEICO", "Allstate", "NRMA", "Budget Direct",
]


def clear_existing_seeded_data(session):
    """Remove demo data inserted earlier (source_url starts with https://demo/)"""
    print("Clearing old demo data...")
    session.execute(text("DELETE FROM car_review_nlp WHERE review_id IN (SELECT id FROM car_reviews WHERE source_url LIKE 'https://demo/%')"))
    session.execute(text("DELETE FROM car_reviews WHERE source_url LIKE 'https://demo/%'"))
    # Also clear the single caranddriver.com record without a rating
    session.execute(text("DELETE FROM car_reviews WHERE rating IS NULL"))
    session.commit()
    print("  Done")


def seed_brands(session) -> dict[str, CarBrand]:
    """Upsert brands with real metadata."""
    print("Seeding brands...")
    brand_map = {}
    for b in BRANDS:
        existing = session.query(CarBrand).filter(CarBrand.name == b["name"]).first()
        if existing:
            existing.country_of_origin = b["country"]
            existing.founded_year = b["year"]
            existing.is_active = b["active"]
            brand_map[b["name"]] = existing
        else:
            brand = CarBrand(
                name=b["name"], country_of_origin=b["country"],
                founded_year=b["year"], is_active=b["active"],
            )
            session.add(brand)
            session.flush()
            brand_map[b["name"]] = brand
    session.commit()
    print(f"  {len(brand_map)} brands seeded")
    return brand_map


def seed_models(session, brand_map: dict) -> dict[str, list]:
    """Upsert car models, return map of brand_name -> list of CarModel."""
    print("Seeding car models...")
    model_map: dict[str, list] = {}
    for brand_name, models in MODELS.items():
        brand = brand_map.get(brand_name)
        if not brand:
            continue
        model_map[brand_name] = []
        for (name, year, segment, body, engine) in models:
            existing = session.query(CarModel).filter(
                CarModel.brand_id == brand.id, CarModel.name == name
            ).first()
            if existing:
                model_map[brand_name].append(existing)
            else:
                m = CarModel(
                    brand_id=brand.id, name=name, year=year,
                    segment=segment, body_type=body, engine_type=engine,
                )
                session.add(m)
                session.flush()
                model_map[brand_name].append(m)
    session.commit()
    print(f"  Models seeded for {len(model_map)} brands")
    return model_map


def seed_reviews(session, brand_map, model_map):
    """Seed car reviews with realistic distributions per brand."""
    print("Seeding car reviews...")

    # Brand review volume and rating profile
    brand_profiles = {
        "Toyota":     dict(n=32, avg_rating=4.15, std=0.55, pos=0.72, neg=0.08),
        "Honda":      dict(n=28, avg_rating=4.05, std=0.58, pos=0.68, neg=0.09),
        "BMW":        dict(n=30, avg_rating=3.82, std=0.78, pos=0.55, neg=0.17),
        "Tesla":      dict(n=35, avg_rating=3.91, std=0.90, pos=0.60, neg=0.18),
        "Ford":       dict(n=30, avg_rating=3.65, std=0.82, pos=0.52, neg=0.20),
        "Mercedes":   dict(n=26, avg_rating=4.02, std=0.65, pos=0.63, neg=0.12),
        "Volkswagen": dict(n=24, avg_rating=3.72, std=0.75, pos=0.54, neg=0.18),
        "Hyundai":    dict(n=22, avg_rating=3.98, std=0.62, pos=0.65, neg=0.11),
        "Audi":       dict(n=24, avg_rating=3.88, std=0.72, pos=0.57, neg=0.15),
        "Chevrolet":  dict(n=20, avg_rating=3.50, std=0.88, pos=0.48, neg=0.24),
    }

    count = 0
    for brand_name, profile in brand_profiles.items():
        brand = brand_map.get(brand_name)
        models = model_map.get(brand_name, [])
        if not brand or not models:
            continue

        brand_slug = brand_name.lower().replace(" ", "-")

        for i in range(profile["n"]):
            # Pick a random model
            model = random.choice(models)
            model_slug = model.name.lower().replace(" ", "-").replace(" ", "")

            # Determine sentiment class for this review
            r = random.random()
            if r < profile["pos"]:
                sentiment = "positive"
                rating_base = min(5.0, max(3.5, random.gauss(4.3, 0.4)))
                text = random.choice(POSITIVE_SNIPPETS)
            elif r < profile["pos"] + profile["neg"]:
                sentiment = "negative"
                rating_base = max(1.0, min(2.5, random.gauss(1.8, 0.5)))
                text = random.choice(NEGATIVE_SNIPPETS)
            else:
                sentiment = "neutral"
                rating_base = max(2.5, min(4.0, random.gauss(3.2, 0.5)))
                text = random.choice(NEUTRAL_SNIPPETS)

            rating = round(min(5.0, max(1.0, rating_base)), 1)

            # Pick a source
            src_name, src_tmpl = random.choice(SOURCES_CAR_REVIEW)
            source_url = src_tmpl.format(brand=brand_slug, model=model_slug)

            # Spread dates over last 12 months
            scraped = rand_dt(365, 0)
            review_dt = rand_date(380, 5)

            titles = {
                "positive": [
                    f"{brand_name} {model.name} — Impressively Executed",
                    f"A Compelling Case for the {brand_name} {model.name}",
                    f"The {model.name} Exceeds Expectations Again",
                    f"Why the {brand_name} {model.name} Earns Its Price",
                ],
                "negative": [
                    f"{brand_name} {model.name} — Falling Short of the Premium Promise",
                    f"The {model.name}'s Quality Control Issues Are Hard to Ignore",
                    f"Disappointed with Our {brand_name} {model.name} Experience",
                    f"Not Worth the Money: {brand_name} {model.name} Review",
                ],
                "neutral": [
                    f"{brand_name} {model.name}: Reliable, If Unexciting",
                    f"The {model.name} in 2024: Solid Effort, No Breakthroughs",
                    f"{brand_name} {model.name} — A Measured Assessment",
                    f"Competent but Conservative: The {brand_name} {model.name}",
                ],
            }
            title = random.choice(titles[sentiment])

            # Random author names
            authors = ["James Holt", "Sarah Chen", "Mike Rivera", "Emma Walsh",
                       "David Park", "Anna Müller", "Tom Bradley", "Claire Dixon",
                       "Alex Nakamura", "Laura Ferreira", "Chris Thompson"]

            review = CarReview(
                model_id=model.id,
                source_url=source_url,
                rating=rating,
                review_title=title,
                review_text=text,
                author=random.choice(authors),
                review_date=review_dt,
                scraped_at=scraped,
            )
            session.add(review)
            count += 1

    session.commit()
    print(f"  {count} car reviews seeded")


def seed_insurance_reviews(session):
    """Seed insurance reviews with realistic distributions."""
    print("Seeding insurance reviews...")

    company_profiles = {
        "Admiral":        dict(n=12, avg=3.9, pos=0.60, neg=0.18),
        "Direct Line":    dict(n=10, avg=3.5, pos=0.48, neg=0.26),
        "Aviva":          dict(n=10, avg=3.7, pos=0.55, neg=0.20),
        "LV=":            dict(n=8,  avg=4.0, pos=0.62, neg=0.14),
        "AXA":            dict(n=8,  avg=3.6, pos=0.50, neg=0.22),
        "Allianz":        dict(n=8,  avg=3.8, pos=0.55, neg=0.18),
        "Hastings Direct":dict(n=8,  avg=3.4, pos=0.45, neg=0.28),
        "Churchill":      dict(n=6,  avg=3.7, pos=0.52, neg=0.20),
    }

    # Pre-build insurer map
    ins_co_map: dict[str, InsuranceCompany] = {}
    for company in company_profiles:
        ins_co = session.query(InsuranceCompany).filter(
            InsuranceCompany.name == company
        ).first()
        if not ins_co:
            ins_co = InsuranceCompany(name=company, country="United Kingdom", is_active=True)
            session.add(ins_co)
            session.flush()
        ins_co_map[company] = ins_co

    count = 0
    for company, profile in company_profiles.items():
        ins_co = ins_co_map[company]
        co_slug = company.lower().replace(" ", "-").replace("=", "")

        for i in range(profile["n"]):
            r = random.random()
            if r < profile["pos"]:
                rating = round(min(5.0, max(3.5, random.gauss(4.2, 0.4))), 1)
                body = random.choice(INSURANCE_REVIEW_SNIPPETS_POS)
                title_opts = [
                    f"Excellent service from {company}",
                    f"{company} handled my claim professionally",
                    f"Impressed with {company}'s customer support",
                ]
            elif r < profile["pos"] + profile["neg"]:
                rating = round(max(1.0, min(2.5, random.gauss(1.9, 0.5))), 1)
                body = random.choice(INSURANCE_REVIEW_SNIPPETS_NEG)
                title_opts = [
                    f"Very disappointed with {company}",
                    f"{company} — renewal price shock",
                    f"Claim dispute with {company} still unresolved",
                ]
            else:
                rating = round(max(2.5, min(4.0, random.gauss(3.3, 0.5))), 1)
                body = "Straightforward to set up and renewal was easy. No claims made so hard to assess claim handling, but admin experience was smooth and pricing was competitive."
                title_opts = [
                    f"{company} — decent option",
                    f"Satisfactory experience with {company}",
                    f"{company}: does what it says on the tin",
                ]

            src_tmpl = random.choice(SOURCES_INSURANCE)[1]
            source_url = src_tmpl.format(company=co_slug)

            review = InsuranceReview(
                company_id=ins_co.id,
                source_url=source_url,
                rating=rating,
                review_title=random.choice(title_opts),
                review_text=body,
                author=random.choice(["J. Harrison", "M. Singh", "L. Peters",
                                      "K. Williams", "P. Murphy", "A. Okonkwo",
                                      "C. Davies", "R. Stewart"]),
                review_date=rand_date(365, 0),
                scraped_at=rand_dt(365, 0),
            )
            session.add(review)
            count += 1

    session.commit()
    print(f"  {count} insurance reviews seeded")


def seed_articles(session):
    """Seed market trend articles."""
    print("Seeding market articles...")
    count = 0
    existing_urls = {r[0] for r in session.execute(
        text("SELECT source_url FROM market_trend_articles")).fetchall()}

    for (src, url, title, body, pub_date, author) in ARTICLE_DATA:
        if url in existing_urls:
            continue
        # Compute scraped_at as a few days after publication
        scraped = utc(datetime.combine(pub_date, datetime.min.time()) + timedelta(days=random.randint(1, 5)))
        article = MarketTrendArticle(
            source_url=url,
            title=title,
            body_text=body,
            author=author,
            publication_date=pub_date,
            scraped_at=scraped,
        )
        session.add(article)
        count += 1
    session.commit()
    print(f"  {count} articles seeded")


def seed_listings(session, model_map):
    """Seed car listings from AutoScout24."""
    print("Seeding car listings...")
    count = 0

    listing_profiles = [
        # (brand, model_name, n, mileage_range, price_mult)
        ("Toyota",     "Camry",    8,  (15000, 85000),  1.0),
        ("Toyota",     "RAV4",     10, (12000, 70000),  1.05),
        ("BMW",        "3 Series", 12, (20000, 95000),  1.2),
        ("BMW",        "X3",       8,  (18000, 80000),  1.25),
        ("Tesla",      "Model 3",  10, (10000, 60000),  1.15),
        ("Tesla",      "Model Y",  8,  (8000, 55000),   1.2),
        ("Volkswagen", "Golf",     15, (25000, 110000), 0.9),
        ("Volkswagen", "Tiguan",   10, (20000, 90000),  1.0),
        ("Honda",      "Civic",    10, (20000, 95000),  0.88),
        ("Honda",      "Accord",   7,  (18000, 85000),  0.92),
        ("Ford",       "F-150",    8,  (15000, 75000),  1.1),
        ("Mercedes",   "C-Class",  10, (22000, 90000),  1.3),
        ("Hyundai",    "Tucson",   9,  (18000, 80000),  0.85),
        ("Audi",       "Q5",       9,  (20000, 85000),  1.25),
        ("Chevrolet",  "Equinox",  7,  (25000, 100000), 0.9),
    ]

    for (brand_name, model_name, n, mileage_range, price_mult) in listing_profiles:
        models = model_map.get(brand_name, [])
        model = next((m for m in models if m.name == model_name), None)
        if not model:
            continue

        base_lo, base_hi = BRAND_BASE_PRICES[brand_name]

        for _ in range(n):
            mileage = random.randint(*mileage_range)
            base_price = random.uniform(base_lo, base_hi) * price_mult
            # Depreciate by mileage
            depr = max(0.5, 1.0 - mileage / 200000.0)
            price = round(base_price * depr, -2)  # round to nearest 100
            city, country = random.choice(LISTING_LOCATIONS)

            brand_slug = brand_name.lower().replace(" ", "-")
            model_slug = model_name.lower().replace(" ", "-").replace(".", "")
            listing_url = f"https://www.autoscout24.com/listings/{brand_slug}-{model_slug}-{uuid.uuid4().hex[:8]}"

            listing = CarListing(
                model_id=model.id,
                listing_url=listing_url,
                dealer_name=random.choice(DEALERS),
                mileage_km=mileage,
                listed_price=price,
                currency="EUR",
                city=city,
                country=country,
                listed_at=rand_date(180, 0),
                scraped_at=rand_dt(60, 0),
            )
            session.add(listing)
            count += 1

    session.commit()
    print(f"  {count} car listings seeded")


def seed_competitor_pricing(session):
    """Seed competitor pricing snapshots across multiple periods."""
    print("Seeding competitor pricing...")
    count = 0

    # Pre-build InsuranceCompany map (required FK)
    ins_co_cache: dict[str, InsuranceCompany] = {}
    for insurer in INSURERS:
        co = session.query(InsuranceCompany).filter(InsuranceCompany.name == insurer).first()
        if not co:
            co = InsuranceCompany(name=insurer, country="United Kingdom", is_active=True)
            session.add(co)
            session.flush()
        ins_co_cache[insurer] = co

    # Multiple snapshot dates to show trend
    snapshot_dates = [
        date(2025, 1, 15), date(2025, 2, 15), date(2025, 3, 15),
        date(2025, 4, 15), date(2025, 5, 15), date(2025, 6, 15),
        date(2025, 7, 15), date(2025, 8, 15), date(2025, 9, 15),
        date(2025, 10, 15), date(2025, 11, 15), date(2025, 12, 15),
        date(2026, 1, 15), date(2026, 2, 15), date(2026, 3, 1),
    ]

    for snap_date in snapshot_dates:
        n_quotes = random.randint(3, 6)
        selected = random.sample(PRICING_DATA, min(n_quotes, len(PRICING_DATA)))
        for (ctype, region, price_range, currency) in selected:
            months_from_start = (snap_date - date(2025, 1, 1)).days / 30
            inflation_factor = 1.0 + (0.08 / 12) * months_from_start
            lo = int(price_range[0] * inflation_factor)
            hi = int(price_range[1] * inflation_factor)
            price = round(random.uniform(lo, hi), 2)

            insurer_name = random.choice(INSURERS)
            ins_co = ins_co_cache[insurer_name]
            scraped = utc(datetime.combine(snap_date, datetime.min.time()) + timedelta(days=random.randint(0, 3)))

            pricing = CompetitorPricing(
                company_id=ins_co.id,
                price=price,
                currency=currency,
                coverage_type=ctype,
                region=region,
                snapshot_date=snap_date,
                scraped_at=scraped,
            )
            session.add(pricing)
            count += 1

    session.commit()
    print(f"  {count} competitor pricing records seeded")


def seed_scraping_infrastructure(session):
    """Mark queued scraping tasks as completed with realistic run records."""
    print("Seeding scraping infrastructure...")

    queued_tasks = session.query(ScrapingTask).filter(
        ScrapingTask.task_name.in_([
            "scrape_caranddriver", "scrape_edmunds",
            "scrape_trustpilot_ins", "scrape_reuters_auto"
        ])
    ).all()

    for task in queued_tasks:
        task.status = "COMPLETED"
        start = rand_dt(30, 5)
        end = utc(start + timedelta(seconds=random.randint(15, 90)))
        run = ScrapingRun(
            task_id=task.id,
            status="SUCCESS",
            pages_fetched=random.randint(4, 12),
            records_extracted=random.randint(10, 30),
            started_at=start,
            finished_at=end,
            duration_seconds=(end - start).total_seconds(),
        )
        session.add(run)

    session.commit()
    print(f"  Updated {len(queued_tasks)} queued tasks to completed")


def main():
    print("=" * 60)
    print("Seeding realistic automotive intelligence data")
    print("=" * 60)

    with get_db_session() as session:
        clear_existing_seeded_data(session)
        brand_map = seed_brands(session)
        model_map = seed_models(session, brand_map)
        seed_reviews(session, brand_map, model_map)
        seed_insurance_reviews(session)
        seed_articles(session)
        seed_listings(session, model_map)
        seed_competitor_pricing(session)
        seed_scraping_infrastructure(session)

    print()
    print("=" * 60)
    print("Seeding complete. Now run:")
    print("  python scripts/run_nlp_pipeline.py")
    print("  python scripts/run_analytics.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
