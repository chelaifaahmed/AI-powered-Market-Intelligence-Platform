"""
scripts/seed_enriched_data.py
--------------------------------
Phase 2 enrichment seed: adds 10 more brands, 60+ more models with full spec
data, 1000+ additional reviews from 9 credible sources, 250+ listings with
color/fuel/trim detail, 90+ articles with categories, and more pricing records.

Designed to work on top of the existing seed_realistic_data.py data — does NOT
delete anything, only inserts new records.

Run from project root:
    python scripts/seed_enriched_data.py
"""

from __future__ import annotations

import sys
import os
import random
import hashlib
from datetime import datetime, timedelta, timezone, date
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_session
from database.models import (
    CarBrand, CarModel, CarReview, InsuranceReview, CarListing,
    MarketTrendArticle, CompetitorPricing, InsuranceCompany,
    ReviewSource, ScrapingTask, ScrapingRun,
)
from database.enums import PipelineStatus
from sqlalchemy import text

random.seed(99)

def utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

def rand_dt(start_days_ago: int, end_days_ago: int = 0) -> datetime:
    days = random.randint(end_days_ago, start_days_ago)
    return utc(datetime.utcnow() - timedelta(
        days=days, hours=random.randint(0, 23), minutes=random.randint(0, 59)
    ))

def rand_date(start_days_ago: int, end_days_ago: int = 0) -> date:
    return rand_dt(start_days_ago, end_days_ago).date()

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

# ---------------------------------------------------------------------------
# 10 new brands (30 total with existing 10)
# ---------------------------------------------------------------------------
NEW_BRANDS = [
    dict(name="Porsche",       country="Germany",     year=1931, active=True),
    dict(name="Volvo",         country="Sweden",      year=1927, active=True),
    dict(name="Nissan",        country="Japan",       year=1933, active=True),
    dict(name="Renault",       country="France",      year=1899, active=True),
    dict(name="Kia",           country="South Korea", year=1944, active=True),
    dict(name="Mazda",         country="Japan",       year=1920, active=True),
    dict(name="Subaru",        country="Japan",       year=1953, active=True),
    dict(name="Peugeot",       country="France",      year=1882, active=True),
    dict(name="Jeep",          country="USA",         year=1941, active=True),
    dict(name="Land Rover",    country="UK",          year=1948, active=True),
]

# ---------------------------------------------------------------------------
# Models per brand — (name, year, segment, body_type, engine_type,
#                     trim, transmission, drivetrain, hp, torque_nm,
#                     battery_kwh, range_km, doors, seats, msrp_eur)
# ---------------------------------------------------------------------------
NEW_MODELS = {
    "Porsche": [
        ("911 Carrera", 2024, "Sports", "Coupe", "Petrol",
         "Carrera S", "PDK", "RWD", 450, 530, None, None, 2, 4, 139900),
        ("Cayenne", 2024, "Full-size SUV", "SUV", "Hybrid",
         "E-Hybrid", "Automatic", "AWD", 462, 700, 25.9, 55, 5, 5, 99800),
        ("Taycan", 2024, "Mid-size", "Sedan", "Electric",
         "Turbo S", "Automatic", "AWD", 761, 1050, 93.4, 504, 4, 5, 185600),
        ("Macan EV", 2024, "Compact SUV", "SUV", "Electric",
         "Turbo", "Automatic", "AWD", 639, 1130, 100.0, 591, 5, 5, 109900),
    ],
    "Volvo": [
        ("XC60", 2024, "Compact SUV", "SUV", "Hybrid",
         "Recharge T8", "Automatic", "AWD", 455, 709, 18.8, 76, 5, 5, 72000),
        ("XC90", 2024, "Full-size SUV", "SUV", "Hybrid",
         "Recharge T8", "Automatic", "AWD", 455, 709, 18.8, 72, 5, 7, 89000),
        ("EX90", 2024, "Full-size SUV", "SUV", "Electric",
         "Twin Motor", "Automatic", "AWD", 517, 910, 111.0, 580, 5, 7, 95000),
        ("C40 Recharge", 2024, "Compact SUV", "SUV", "Electric",
         "Twin Motor", "Automatic", "AWD", 408, 670, 82.0, 476, 5, 5, 59000),
    ],
    "Nissan": [
        ("Ariya", 2024, "Compact SUV", "SUV", "Electric",
         "Advance", "Automatic", "AWD", 394, 600, 91.0, 489, 5, 5, 57000),
        ("Leaf", 2024, "Compact", "Hatchback", "Electric",
         "e+", "Automatic", "FWD", 217, 340, 59.0, 340, 5, 5, 37000),
        ("Qashqai", 2024, "Compact SUV", "SUV", "Hybrid",
         "e-Power", "CVT", "FWD", 190, 330, None, None, 5, 5, 38000),
        ("GT-R", 2024, "Sports", "Coupe", "Petrol",
         "NISMO", "DCT", "AWD", 600, 652, None, None, 2, 4, 130000),
    ],
    "Renault": [
        ("Megane E-Tech", 2024, "Compact", "Hatchback", "Electric",
         "EV60", "Automatic", "FWD", 218, 300, 60.0, 450, 5, 5, 42000),
        ("Zoe", 2024, "Compact", "Hatchback", "Electric",
         "R135", "Automatic", "FWD", 135, 245, 52.0, 390, 5, 5, 33000),
        ("Austral", 2024, "Compact SUV", "SUV", "Hybrid",
         "E-Tech", "Automatic", "FWD", 200, 230, None, None, 5, 5, 40000),
        ("Clio", 2024, "Subcompact", "Hatchback", "Petrol",
         "RS Line", "Manual", "FWD", 130, 240, None, None, 5, 5, 24000),
    ],
    "Kia": [
        ("EV6", 2024, "Compact", "Crossover", "Electric",
         "GT-Line AWD", "Automatic", "AWD", 577, 740, 77.4, 506, 5, 5, 60000),
        ("Sportage", 2024, "Compact SUV", "SUV", "Hybrid",
         "HEV", "Automatic", "AWD", 230, 350, None, None, 5, 5, 41000),
        ("Niro EV", 2024, "Compact SUV", "SUV", "Electric",
         "EV", "Automatic", "FWD", 204, 255, 64.8, 463, 5, 5, 44000),
        ("Stinger", 2024, "Mid-size", "Sedan", "Petrol",
         "GT2", "Automatic", "AWD", 368, 510, None, None, 4, 5, 55000),
    ],
    "Mazda": [
        ("CX-5", 2024, "Compact SUV", "SUV", "Petrol",
         "Signature", "Automatic", "AWD", 227, 420, None, None, 5, 5, 42000),
        ("MX-5", 2024, "Sports", "Roadster", "Petrol",
         "RF Grand Touring", "Manual", "RWD", 181, 205, None, None, 2, 2, 40000),
        ("CX-60", 2024, "Mid-size SUV", "SUV", "Hybrid",
         "PHEV", "Automatic", "AWD", 327, 500, 17.8, 61, 5, 5, 56000),
        ("Mazda3", 2024, "Compact", "Hatchback", "Petrol",
         "Turbo", "Automatic", "AWD", 227, 420, None, None, 5, 5, 35000),
    ],
    "Subaru": [
        ("Outback", 2024, "Mid-size SUV", "SUV", "Petrol",
         "Limited XT", "CVT", "AWD", 260, 376, None, None, 5, 5, 42000),
        ("Forester", 2024, "Compact SUV", "SUV", "Hybrid",
         "e-BOXER", "CVT", "AWD", 150, 300, None, None, 5, 5, 37000),
        ("WRX", 2024, "Compact", "Sedan", "Petrol",
         "GT", "CVT", "AWD", 271, 350, None, None, 4, 5, 40000),
        ("Solterra", 2024, "Compact SUV", "SUV", "Electric",
         "ET-SE", "Automatic", "AWD", 218, 336, 71.4, 466, 5, 5, 52000),
    ],
    "Peugeot": [
        ("e-208", 2024, "Subcompact", "Hatchback", "Electric",
         "GT", "Automatic", "FWD", 156, 260, 51.0, 362, 5, 5, 35000),
        ("e-2008", 2024, "Subcompact SUV", "SUV", "Electric",
         "GT", "Automatic", "FWD", 156, 260, 54.0, 400, 5, 5, 40000),
        ("408", 2024, "Compact", "Fastback", "Hybrid",
         "PHEV", "Automatic", "FWD", 225, 360, 12.4, 55, 5, 5, 46000),
        ("3008 EV", 2024, "Compact SUV", "SUV", "Electric",
         "Long Range", "Automatic", "FWD", 231, 343, 96.9, 700, 5, 5, 48000),
    ],
    "Jeep": [
        ("Wrangler", 2024, "Off-road SUV", "SUV", "Hybrid",
         "4xe Rubicon", "Automatic", "4WD", 375, 637, 17.0, 56, 4, 5, 60000),
        ("Grand Cherokee", 2024, "Mid-size SUV", "SUV", "Hybrid",
         "4xe", "Automatic", "4WD", 375, 637, 17.0, 51, 5, 5, 72000),
        ("Avenger EV", 2024, "Subcompact SUV", "SUV", "Electric",
         "Summit", "Automatic", "FWD", 156, 260, 54.0, 392, 5, 5, 40000),
        ("Compass", 2024, "Compact SUV", "SUV", "Petrol",
         "S", "Automatic", "FWD", 150, 240, None, None, 5, 5, 35000),
    ],
    "Land Rover": [
        ("Defender", 2024, "Off-road SUV", "SUV", "Petrol",
         "P400 X", "Automatic", "AWD", 400, 550, None, None, 5, 5, 115000),
        ("Range Rover", 2024, "Full-size SUV", "SUV", "Hybrid",
         "P510e", "Automatic", "AWD", 510, 700, 31.8, 113, 5, 7, 180000),
        ("Discovery", 2024, "Full-size SUV", "SUV", "Diesel",
         "D300 R-Dynamic", "Automatic", "AWD", 300, 650, None, None, 5, 7, 87000),
        ("Range Rover Sport", 2024, "Mid-size SUV", "SUV", "Hybrid",
         "P460e", "Automatic", "AWD", 460, 620, 31.8, 113, 5, 5, 120000),
    ],
}

# Also update existing brand models with spec data
EXISTING_MODEL_SPECS = {
    # (brand_name, model_name) -> (trim, transmission, drivetrain, hp, torque, batt, range, doors, seats, msrp)
    ("Toyota", "Camry"):    ("XSE V6",   "Automatic", "FWD", 301, 362, None, None, 4, 5, 31000),
    ("Toyota", "Corolla"):  ("XSE",      "CVT",       "FWD", 169, 204, None, None, 4, 5, 25000),
    ("Toyota", "RAV4"):     ("TRD Off-Road", "Automatic", "AWD", 203, 247, None, None, 5, 5, 34000),
    ("Toyota", "Prius"):    ("Prime SE",  "CVT",       "AWD", 220, 210, 13.6, 69, 4, 5, 34000),
    ("BMW", "3 Series"):    ("M340i xDrive", "Automatic", "AWD", 382, 500, None, None, 4, 5, 58000),
    ("BMW", "5 Series"):    ("530i xDrive",  "Automatic", "AWD", 245, 400, None, None, 4, 5, 65000),
    ("BMW", "X3"):          ("xDrive30i",    "Automatic", "AWD", 248, 350, None, None, 5, 5, 53000),
    ("BMW", "M4"):          ("Competition",  "DCT",       "AWD", 530, 650, None, None, 2, 4, 95000),
    ("Tesla", "Model 3"):   ("Long Range AWD", "Automatic", "AWD", 358, 493, 82.0, 602, 4, 5, 51000),
    ("Tesla", "Model Y"):   ("Long Range AWD", "Automatic", "AWD", 384, 493, 82.0, 533, 5, 5, 55000),
    ("Tesla", "Model S"):   ("Plaid",        "Automatic", "AWD", 1020, 1420, 100.0, 628, 4, 5, 108000),
    ("Tesla", "Model X"):   ("Plaid",        "Automatic", "AWD", 1020, 1420, 100.0, 543, 5, 7, 115000),
    ("Ford", "F-150"):      ("Lariat",       "Automatic", "4WD", 400, 500, None, None, 4, 5, 55000),
    ("Ford", "Mustang"):    ("GT Premium",   "Manual",    "RWD", 450, 529, None, None, 2, 4, 45000),
    ("Honda", "Civic"):     ("Sport Touring", "CVT",     "FWD", 158, 185, None, None, 4, 5, 28000),
    ("Honda", "CR-V"):      ("Sport Hybrid",  "Automatic","AWD", 204, 247, None, None, 5, 5, 36000),
    ("Mercedes", "C-Class"):("C300 4MATIC",  "Automatic", "AWD", 255, 400, None, None, 4, 5, 52000),
    ("Mercedes", "E-Class"):("E450 4MATIC",  "Automatic", "AWD", 362, 500, None, None, 4, 5, 70000),
    ("Volkswagen", "Golf"): ("GTI",          "DCT",       "FWD", 241, 370, None, None, 4, 5, 33000),
    ("Volkswagen", "Tiguan"):("R-Line",       "Automatic","AWD", 184, 320, None, None, 5, 5, 38000),
    ("Hyundai", "Ioniq 5"): ("AWD Long Range","Automatic","AWD", 320, 605, 77.4, 507, 5, 5, 52000),
    ("Hyundai", "Tucson"):  ("N Line AWD",   "Automatic", "AWD", 187, 234, None, None, 5, 5, 36000),
    ("Audi", "A4"):         ("45 TFSI quattro","Automatic","AWD",261, 400, None, None, 4, 5, 52000),
    ("Audi", "Q5"):         ("55 TFSI e",     "Automatic","AWD",367, 500, 14.4, 63, 5, 5, 68000),
    ("Chevrolet", "Silverado"):("LTZ",        "Automatic","4WD",420, 623, None, None, 4, 5, 57000),
    ("Chevrolet", "Equinox EV"):("RS AWD",    "Automatic","AWD",290, 440, 85.0, 515, 5, 5, 48000),
}

# ---------------------------------------------------------------------------
# Review sources — 9 credible automotive publications
# ---------------------------------------------------------------------------
SOURCES = [
    dict(name="Car and Driver",   url="https://www.caranddriver.com",  reliability=0.96),
    dict(name="Edmunds",          url="https://www.edmunds.com",        reliability=0.95),
    dict(name="MotorTrend",       url="https://www.motortrend.com",     reliability=0.95),
    dict(name="Top Gear",         url="https://www.topgear.com",        reliability=0.94),
    dict(name="Road and Track",   url="https://www.roadandtrack.com",   reliability=0.93),
    dict(name="Kelley Blue Book", url="https://www.kbb.com",            reliability=0.92),
    dict(name="Auto Express",     url="https://www.autoexpress.co.uk",  reliability=0.92),
    dict(name="Autoblog",         url="https://www.autoblog.com",       reliability=0.90),
    dict(name="Jalopnik",         url="https://jalopnik.com",           reliability=0.88),
    dict(name="Reuters",          url="https://www.reuters.com",        reliability=0.97),
    dict(name="Automotive News",  url="https://www.autonews.com",       reliability=0.95),
    dict(name="Bloomberg",        url="https://www.bloomberg.com",      reliability=0.96),
    dict(name="Trustpilot",       url="https://www.trustpilot.com",     reliability=0.82),
    dict(name="AutoScout24",      url="https://www.autoscout24.com",    reliability=0.88),
    dict(name="Mobile.de",        url="https://www.mobile.de",          reliability=0.87),
]

# ---------------------------------------------------------------------------
# Brand rating profiles (avg, std) — credibility-differentiated
# ---------------------------------------------------------------------------
BRAND_RATINGS = {
    "Porsche":     (4.7, 0.3),
    "Volvo":       (4.3, 0.4),
    "Nissan":      (3.7, 0.5),
    "Renault":     (3.6, 0.5),
    "Kia":         (4.1, 0.4),
    "Mazda":       (4.2, 0.4),
    "Subaru":      (4.2, 0.4),
    "Peugeot":     (3.8, 0.5),
    "Jeep":        (3.6, 0.6),
    "Land Rover":  (3.5, 0.7),
    # Existing brands (update existing data spec only)
    "Toyota":      (4.1, 0.4),
    "BMW":         (4.5, 0.3),
    "Tesla":       (3.9, 0.6),
    "Ford":        (3.7, 0.5),
    "Honda":       (4.0, 0.4),
    "Mercedes":    (4.4, 0.4),
    "Volkswagen":  (3.9, 0.4),
    "Hyundai":     (4.0, 0.4),
    "Audi":        (4.3, 0.3),
    "Chevrolet":   (3.6, 0.5),
}

# ---------------------------------------------------------------------------
# Pros/cons per brand archetype
# ---------------------------------------------------------------------------
PROS_CONS = {
    "Porsche":    (["Exceptional performance", "Premium build quality", "Precise handling",
                    "Iconic design", "Strong residual value"],
                   ["Very expensive", "Small interior", "High running costs"]),
    "Volvo":      (["Excellent safety ratings", "Refined interior", "Comfortable ride",
                    "Strong EV lineup", "Scandinavian design"],
                   ["Expensive options", "Reliability concerns", "Limited sportiness"]),
    "Nissan":     (["Good value", "Practical cabin", "Efficient engines",
                    "Comfortable ride", "EV pioneer (Leaf)"],
                   ["Dated interior on some models", "CVT can feel sluggish", "Brand image"]),
    "Renault":    (["French flair", "Good EV range", "Practical layouts",
                    "Affordable pricing", "Good fuel economy"],
                   ["Reliability concerns", "Weak US presence", "Firm ride on some models"]),
    "Kia":        (["Outstanding warranty", "Great value", "Modern interiors",
                    "Strong EV offering", "Bold design"],
                   ["Brand perception still catching up", "Less prestige", "Some CVT issues"]),
    "Mazda":      (["Driver-focused dynamics", "Premium feel for price", "Reliable engines",
                    "Beautiful design", "Efficient Skyactiv tech"],
                   ["Limited EV lineup", "Smaller cabin than rivals", "No third row"]),
    "Subaru":     (["Standard AWD", "Strong safety ratings", "Reliable engines",
                    "Good off-road capability", "Loyal community"],
                   ["CVT-heavy lineup", "Interior quality lags", "Noisy cabin at speed"]),
    "Peugeot":    (["Distinctive French design", "Comfortable ride", "Good EV range",
                    "i-Cockpit interface", "Competitive pricing"],
                   ["Limited US availability", "Polarizing cockpit ergonomics", "Some reliability concerns"]),
    "Jeep":       (["Iconic off-road capability", "Strong brand identity", "Open-air options",
                    "Competitive PHEV", "Practical interiors"],
                   ["Below-average reliability", "Fuel economy concerns", "Premium pricing for some trims"]),
    "Land Rover": (["Unmatched off-road ability", "Luxurious interiors", "Strong towing capacity",
                    "Distinctive design", "PHEV options"],
                   ["Poor long-term reliability", "Expensive maintenance", "High running costs"]),
}

# Default for existing brands
DEFAULT_PROS_CONS = {
    "Toyota":     (["Legendary reliability", "Excellent resale value", "Efficient engines"],
                   ["Conservative styling", "Less sporty dynamics", "Some models outdated"]),
    "BMW":        (["Outstanding driving dynamics", "Premium interior", "Powerful engines"],
                   ["Expensive options", "Complex iDrive", "High maintenance costs"]),
    "Tesla":      (["Industry-leading range", "OTA updates", "Performance"],
                   ["Build quality inconsistency", "Panel gaps", "Service network"]),
    "Ford":       (["Tough and capable", "Good value", "Wide dealer network"],
                   ["Interior quality varies", "Fuel economy", "Some reliability issues"]),
    "Honda":      (["Reliable", "Spacious cabin", "Good fuel economy"],
                   ["Uninspiring styling", "CVT in most models", "Slow updates"]),
    "Mercedes":   (["Luxurious interior", "Smooth ride", "MBUX system"],
                   ["High cost of ownership", "Complex options", "Depreciation"]),
    "Volkswagen": (["Solid build quality", "Refined driving", "Practical"],
                   ["DSG issues on some models", "Expensive options", "Service costs"]),
    "Hyundai":    (["Long warranty", "Modern tech", "Good value"],
                   ["Reliability questions on newer models", "Some engines recalled", "Residual values"]),
    "Audi":       (["Premium interior quality", "Quattro AWD", "Smooth engines"],
                   ["Complex electronics", "Expensive to maintain", "Heavy weight"]),
    "Chevrolet":  (["American muscle heritage", "Good capability", "Value trims"],
                   ["Reliability", "Interior quality", "Fuel economy"]),
}

# ---------------------------------------------------------------------------
# Review templates per source type
# ---------------------------------------------------------------------------
CAR_REVIEW_TEMPLATES = [
    "The {model} is one of the most compelling options in its segment. {pros_text}. On the downside, {cons_text}. Overall, a strong recommendation for buyers who prioritize {focus}.",
    "We spent two weeks with the {model} and came away impressed by its {strength}. The {trim} variant we tested delivered {hp}hp through {transmission} to all four wheels. {pros_text}. That said, {cons_text}.",
    "If you're cross-shopping in the {segment} segment, the {model} deserves serious consideration. Its {strength} is genuinely class-leading. {pros_text}. The main criticism remains {cons_text}.",
    "Few cars balance {quality1} and {quality2} as well as the {model}. Our extended test in the {trim} specification confirmed the hype. {pros_text}, though {cons_text}.",
    "The redesigned {model} raises the bar significantly. Driving it back-to-back with rivals makes clear just how far {brand} has come. {pros_text}. The {cons_text} remains a sticking point for some buyers.",
    "From cold start to highway cruising, the {model} impresses with its refinement and capability. {pros_text}. We wish {cons_text} were addressed in this refresh cycle.",
    "At its price point, the {model} offers exceptional value. The {trim} specification we evaluated covers the essentials while keeping costs reasonable. {pros_text}. Don't overlook {cons_text} when making your decision.",
    "The {model} is the answer for drivers who want {quality1} without sacrificing {quality2}. {brand}'s engineers have clearly listened to customer feedback. {pros_text}. Only {cons_text} holds it back from a top-tier recommendation.",
]

# ---------------------------------------------------------------------------
# Article definitions — category, source, title templates, region
# ---------------------------------------------------------------------------
ARTICLE_CATEGORIES = {
    "EV": [
        ("Reuters",          "Electric vehicle sales surge {pct}% in {region} as charging infrastructure expands",    "Global"),
        ("Bloomberg",        "Battery costs fall to record low, boosting EV profitability for automakers",             "Global"),
        ("Automotive News",  "{brand} announces {model} EV with {range}km range for {year} launch",                    "Global"),
        ("Reuters",          "Europe's EV market share hits {pct}% amid tightening emissions rules",                   "Europe"),
        ("Bloomberg",        "Solid-state battery breakthrough promises double the range by {year}",                    "Global"),
        ("Automotive News",  "Charging network investment tops ${bn}bn as range anxiety fades",                         "North America"),
        ("Reuters",          "China EV makers intensify European push as tariff negotiations continue",                  "Europe"),
        ("Bloomberg",        "Grid capacity upgrades critical as EV adoption accelerates in urban centres",             "Global"),
        ("Automotive News",  "Fleet electrification drives commercial EV demand to record high in Q1 {year}",          "Global"),
        ("Reuters",          "New EU battery regulation mandates end-of-life recycling standards from {year}",          "Europe"),
    ],
    "Market": [
        ("Reuters",          "Global auto sales recover to pre-pandemic levels with {pct}% gain",                      "Global"),
        ("Bloomberg",        "Semiconductor shortage eases; automakers rebuild depleted inventories",                   "Global"),
        ("Automotive News",  "Used car prices normalise as new vehicle supply improves across Europe",                  "Europe"),
        ("Reuters",          "Car subscription services grow {pct}% as consumers embrace flexible ownership",           "Global"),
        ("Bloomberg",        "Automaker margins under pressure as raw material costs remain elevated",                   "Global"),
        ("Automotive News",  "SUV segment captures {pct}% of total new car sales in latest industry data",             "Global"),
        ("Reuters",          "Luxury automotive segment outperforms mass market amid strong demand for premium models", "Global"),
        ("Bloomberg",        "Auto financing rates stabilise after central bank policy pause",                           "North America"),
        ("Automotive News",  "Dealer inventory levels return to normal after three years of shortage",                  "North America"),
        ("Reuters",          "Connected car services generate $1bn+ revenue stream for leading automakers",             "Global"),
    ],
    "Technology": [
        ("Reuters",          "Level 3 autonomous driving approved for highway use in Germany and Japan",                "Europe"),
        ("Bloomberg",        "AI-powered driver assistance cuts accident rates by {pct}% in pilot programmes",          "Global"),
        ("Automotive News",  "Software-defined vehicles reshape OEM revenue model with over-the-air monetisation",     "Global"),
        ("Reuters",          "Vehicle-to-grid technology enables EVs to power homes during peak demand",                "Global"),
        ("Bloomberg",        "Lidar costs drop {pct}% making autonomous systems viable for mass market",               "Global"),
        ("Automotive News",  "Infotainment systems with ChatGPT integration roll out across {brand} lineup",           "Global"),
        ("Reuters",          "Augmented reality HUDs become standard in premium segment by {year}",                    "Global"),
        ("Bloomberg",        "5G connectivity enables real-time traffic routing and predictive maintenance",             "Global"),
        ("Automotive News",  "Digital key adoption grows as automakers phase out traditional key fobs",                 "Global"),
        ("Reuters",          "Thermal management advances extend EV battery life by {pct}% in cold climates",          "Global"),
    ],
    "Manufacturing": [
        ("Reuters",          "{brand} invests ${bn}bn in new EV manufacturing plant creating {jobs}k jobs",            "Global"),
        ("Bloomberg",        "Gigafactory capacity doubles as battery cell demand outpaces projections",                "Global"),
        ("Automotive News",  "Nearshoring trend accelerates as automakers restructure supply chains",                   "Europe"),
        ("Reuters",          "Carbon-neutral manufacturing targets set by leading OEMs for {year}",                    "Global"),
        ("Bloomberg",        "Aluminium and steel use optimised through AI-driven lightweighting programmes",           "Global"),
        ("Automotive News",  "Joint venture battery plants reshape competitive landscape in Europe and US",             "Global"),
        ("Reuters",          "Automation rates hit {pct}% in leading assembly plants as labour costs rise",            "Global"),
        ("Bloomberg",        "Modular vehicle platforms cut development costs by {pct}% across model ranges",          "Global"),
        ("Automotive News",  "Circular economy initiatives recover {pct}% of end-of-life vehicle materials",          "Global"),
        ("Reuters",          "Hydrogen fuel cell vehicles enter commercial production for heavy-duty segment",          "Global"),
    ],
    "Regulation": [
        ("Reuters",          "EU 2035 ICE ban confirmed as member states reach final compromise",                       "Europe"),
        ("Bloomberg",        "US EPA tightens emissions standards pushing automakers toward electrification",           "North America"),
        ("Automotive News",  "Euro 7 standards finalized with new limits on brake and tyre particulate emissions",     "Europe"),
        ("Reuters",          "China mandates 40% NEV sales quota for automakers operating in domestic market",          "Asia"),
        ("Bloomberg",        "UK zero-emission vehicle mandate requires {pct}% of new cars to be electric by {year}",  "Europe"),
        ("Automotive News",  "Right-to-repair legislation challenges OEM software control over connected vehicles",     "Global"),
        ("Reuters",          "Carbon border adjustment hits imported vehicles with higher ICE content from {year}",     "Europe"),
        ("Bloomberg",        "Crash test standards updated globally to include EV-specific battery safety protocols",   "Global"),
        ("Automotive News",  "Data privacy rules reshape in-vehicle connectivity and user tracking practices",          "Global"),
        ("Reuters",          "Aviation biofuel standards influence automotive sustainable fuel roadmap",                 "Global"),
    ],
    "Insurance": [
        ("Reuters",          "EV insurance premiums fall {pct}% as repair data improves actuarial models",             "Global"),
        ("Bloomberg",        "Telematics-based insurance now covers {pct}% of new car owners in the UK",               "Europe"),
        ("Reuters",          "Connected car data transforms underwriting as real-time driving scores go mainstream",    "Global"),
        ("Bloomberg",        "Repair cost inflation forces insurers to revise premium models across Europe",            "Europe"),
        ("Reuters",          "Autonomous vehicle liability framework proposed by EU insurance regulators",              "Europe"),
        ("Bloomberg",        "Pay-per-mile insurance gains traction among urban drivers with low annual mileage",      "Global"),
        ("Reuters",          "Climate change drives {pct}% increase in automotive weather-related claims",             "Global"),
        ("Bloomberg",        "Cyber insurance for connected vehicles emerges as new product category",                  "Global"),
    ],
}

ARTICLE_AUTHORS = {
    "Reuters":         ["David Shepardson", "Paul Lienert", "Nick Carey", "Joe White", "Nora Buli"],
    "Bloomberg":       ["Keith Naughton", "Kyle Stock", "Craig Trudell", "Hannah Recht", "Ed Hammond"],
    "Automotive News": ["Michael Martinez", "Laurence Iliff", "Mark Rechtin", "Breana Noble", "Jamie LaReau"],
}

# ---------------------------------------------------------------------------
# Listing details
# ---------------------------------------------------------------------------
COLORS = ["Pearl White", "Midnight Black", "Deep Blue", "Platinum Silver", "Racing Red",
          "Forest Green", "Burnt Orange", "Champagne Gold", "Cosmic Grey", "Alpine White",
          "Obsidian Black", "Glacier Blue", "Titanium Grey", "Candy Red", "Electric Blue"]

FUEL_TYPES = {
    "Electric": "Electric",
    "Hybrid":   "Hybrid",
    "Petrol":   "Petrol",
    "Diesel":   "Diesel",
}

EUROPEAN_CITIES = [
    ("London",    "UK",          "GBP"),
    ("Manchester","UK",          "GBP"),
    ("Berlin",    "Germany",     "EUR"),
    ("Munich",    "Germany",     "EUR"),
    ("Hamburg",   "Germany",     "EUR"),
    ("Paris",     "France",      "EUR"),
    ("Lyon",      "France",      "EUR"),
    ("Amsterdam", "Netherlands", "EUR"),
    ("Rotterdam", "Netherlands", "EUR"),
    ("Madrid",    "Spain",       "EUR"),
    ("Barcelona", "Spain",       "EUR"),
    ("Milan",     "Italy",       "EUR"),
    ("Rome",      "Italy",       "EUR"),
    ("Vienna",    "Austria",     "EUR"),
    ("Brussels",  "Belgium",     "EUR"),
    ("Zurich",    "Switzerland", "CHF"),
    ("Stockholm", "Sweden",      "SEK"),
    ("Oslo",      "Norway",      "NOK"),
    ("Copenhagen","Denmark",     "DKK"),
    ("Warsaw",    "Poland",      "PLN"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_or_create_source(session, name: str, url: str, reliability: float):
    src = session.query(ReviewSource).filter(ReviewSource.name == name).first()
    if not src:
        src = ReviewSource(name=name, base_url=url, reliability_score=reliability, is_active=True)
        session.add(src)
        session.flush()
    return src

def get_or_create_brand(session, name: str, country: str, year: int) -> CarBrand:
    brand = session.query(CarBrand).filter(CarBrand.name == name).first()
    if not brand:
        brand = CarBrand(name=name, country_of_origin=country, founded_year=year, is_active=True)
        session.add(brand)
        session.flush()
    return brand

def get_or_create_model(session, brand_id, name: str, year: int, segment: str,
                         body_type: str, engine_type: str,
                         trim_level=None, transmission=None, drivetrain=None,
                         hp=None, torque=None, battery_kwh=None, range_km=None,
                         doors=None, seats=None, msrp_eur=None) -> CarModel:
    model = session.query(CarModel).filter(
        CarModel.brand_id == brand_id,
        CarModel.name == name,
        CarModel.year == year
    ).first()
    if not model:
        model = CarModel(
            brand_id=brand_id, name=name, year=year, segment=segment,
            body_type=body_type, engine_type=engine_type,
            trim_level=trim_level, transmission=transmission, drivetrain=drivetrain,
            horsepower_hp=hp, torque_nm=torque, battery_kwh=battery_kwh,
            range_km=range_km, doors=doors, seats=seats, msrp_eur=msrp_eur,
            is_active=True,
        )
        session.add(model)
        session.flush()
    else:
        # Enrich existing model with spec data if missing
        changed = False
        for attr, val in [
            ("trim_level", trim_level), ("transmission", transmission),
            ("drivetrain", drivetrain), ("horsepower_hp", hp),
            ("torque_nm", torque), ("battery_kwh", battery_kwh),
            ("range_km", range_km), ("doors", doors), ("seats", seats),
            ("msrp_eur", msrp_eur),
        ]:
            if val is not None and getattr(model, attr) is None:
                setattr(model, attr, val)
                changed = True
        if changed:
            session.flush()
    return model

def make_review_text(brand: str, model_name: str, trim: str, hp: Optional[int],
                     transmission: Optional[str], segment: str,
                     pros: list, cons: list) -> tuple[str, str, str, str]:
    """Returns (review_text, pros_str, cons_str, variant_tested)"""
    pros_sample = random.sample(pros, min(3, len(pros)))
    cons_sample = random.sample(cons, min(2, len(cons)))
    pros_text = "; ".join(pros_sample)
    cons_text = "; ".join(cons_sample)
    qualities = ["performance", "efficiency", "comfort", "reliability", "tech", "value", "dynamics"]
    tmpl = random.choice(CAR_REVIEW_TEMPLATES)
    text = tmpl.format(
        model=f"{brand} {model_name}",
        brand=brand,
        trim=trim or "base",
        hp=hp or "N/A",
        transmission=transmission or "automatic",
        segment=segment,
        strength=random.choice(["performance envelope", "interior refinement", "EV efficiency", "driving dynamics", "technology package"]),
        quality1=random.choice(qualities),
        quality2=random.choice(qualities),
        pros_text=pros_text,
        cons_text=cons_text,
        focus=random.choice(["reliability", "performance", "efficiency", "value"]),
    )
    return text, pros_text, cons_text, trim or f"{model_name} {random.randint(2023, 2024)}"


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def update_existing_model_specs(session):
    """Backfill spec data onto existing models."""
    print("  Updating existing model specs...")
    updated = 0
    for (brand_name, model_name), spec in EXISTING_MODEL_SPECS.items():
        trim, trans, drive, hp, torq, batt, rng, drs, sts, msrp = spec
        brand = session.query(CarBrand).filter(CarBrand.name == brand_name).first()
        if not brand:
            continue
        models = session.query(CarModel).filter(
            CarModel.brand_id == brand.id,
            CarModel.name == model_name
        ).all()
        for m in models:
            changed = False
            for attr, val in [
                ("trim_level", trim), ("transmission", trans), ("drivetrain", drive),
                ("horsepower_hp", hp), ("torque_nm", torq), ("battery_kwh", batt),
                ("range_km", rng), ("doors", drs), ("seats", sts), ("msrp_eur", msrp),
            ]:
                if val is not None and getattr(m, attr) is None:
                    setattr(m, attr, val)
                    changed = True
            if changed:
                updated += 1
    session.flush()
    print(f"    Updated specs on {updated} existing models")


def seed_new_brands_and_models(session) -> dict:
    """Returns {brand_name: {model_name: model_obj}}"""
    print("  Seeding new brands and models...")
    source_map = {}
    for s in SOURCES:
        source_map[s["name"]] = get_or_create_source(session, s["name"], s["url"], s["reliability"])

    brand_model_map = {}
    for bd in NEW_BRANDS:
        brand = get_or_create_brand(session, bd["name"], bd["country"], bd["year"])
        brand_model_map[bd["name"]] = {}
        for spec in NEW_MODELS.get(bd["name"], []):
            (mname, yr, seg, body, eng, trim, trans, drive, hp, torq, batt, rng, drs, sts, msrp) = spec
            m = get_or_create_model(
                session, brand.id, mname, yr, seg, body, eng,
                trim_level=trim, transmission=trans, drivetrain=drive,
                hp=hp, torque=torq, battery_kwh=batt, range_km=rng,
                doors=drs, seats=sts, msrp_eur=msrp
            )
            brand_model_map[bd["name"]][mname] = m

    session.commit()
    print(f"    Created {len(NEW_BRANDS)} new brands with {sum(len(v) for v in brand_model_map.values())} models")
    return brand_model_map


def seed_car_reviews(session, brand_model_map: dict, source_map: dict):
    """Seed ~100 reviews per new brand across 9 sources = ~1000 reviews."""
    print("  Seeding car reviews for new brands...")
    review_sources = [s for s in [
        "Car and Driver", "Edmunds", "MotorTrend", "Top Gear",
        "Road and Track", "Kelley Blue Book", "Auto Express", "Autoblog", "Jalopnik"
    ] if s in source_map]

    authors_by_source = {
        "Car and Driver":   ["Ezra Dyer", "Tony Quiroga", "Dave VanderWerp", "Kim Reynolds"],
        "Edmunds":          ["Alistair Weaver", "Carlos Lago", "Mark Takahashi", "Brent Romans"],
        "MotorTrend":       ["Jonny Lieberman", "Christian Seabaugh", "Scott Evans", "Allyson Harwood"],
        "Top Gear":         ["Jack Rix", "Rowan Horncastle", "Ollie Kew", "Sam Philip"],
        "Road and Track":   ["Rob Kinnan", "Travis Okulski", "Chris Perkins", "Greg Fink"],
        "Kelley Blue Book": ["Matt Degen", "Brian Moody", "Alain Noa", "Sean Szymkowski"],
        "Auto Express":     ["Steve Fowler", "Jim Holder", "John McIlroy", "Rory Reid"],
        "Autoblog":         ["Joel Stocksdale", "Jake Lingeman", "James Riswick", "Dan Edmunds"],
        "Jalopnik":         ["Jason Torchinsky", "David Tracy", "Patrick George", "Raphael Orlove"],
    }

    inserted = 0
    for brand_name, models in brand_model_map.items():
        avg_r, std_r = BRAND_RATINGS.get(brand_name, (3.8, 0.5))
        pros_list, cons_list = PROS_CONS.get(brand_name, (["Quality product", "Good value"], ["Could improve some aspects"]))

        for model_name, model_obj in models.items():
            reviews_per_model = random.randint(20, 30)
            for _ in range(reviews_per_model):
                src_name = random.choice(review_sources)
                src_obj = source_map[src_name]
                domain = src_obj.base_url.replace("https://www.", "").replace("https://", "")
                author = random.choice(authors_by_source.get(src_name, ["Staff Writer"]))

                # Build URL
                slug = model_name.lower().replace(" ", "-")
                url_suffix = random.randint(100000, 999999)
                source_url = f"{src_obj.base_url}/reviews/{brand_name.lower()}/{slug}/{url_suffix}"

                rating = round(min(5.0, max(1.0, random.gauss(avg_r, std_r))), 1)
                review_date = rand_date(540, 7)
                review_text, pros_str, cons_str, variant = make_review_text(
                    brand_name, model_name,
                    model_obj.trim_level or "",
                    model_obj.horsepower_hp,
                    model_obj.transmission,
                    model_obj.segment or "segment",
                    pros_list, cons_list,
                )
                title_templates = [
                    f"{brand_name} {model_name} Review: {random.choice(['Worth Every Penny', 'Class Leader', 'Surprisingly Capable', 'The Benchmark', 'A Strong Contender'])}",
                    f"{brand_name} {model_name} Long-Term Test: {random.choice(['12 Months', '6 Months', 'Year-Long']) } Update",
                    f"First Drive: {brand_name} {model_name} {model_obj.year or 2024}",
                    f"{brand_name} {model_name} vs. The Competition: Who Wins?",
                    f"Tested: {brand_name} {model_name} {model_obj.trim_level or ''}",
                ]
                title = random.choice(title_templates)
                h = sha256(f"{source_url}|{brand_name}|{model_name}|{author}")

                if session.query(CarReview).filter(CarReview.content_hash == h).first():
                    continue

                scraped = rand_dt(540, 5)
                # Ensure scraped_at is in valid partition range
                year = scraped.year
                if year < 2024: scraped = scraped.replace(year=2024)
                if year > 2027: scraped = scraped.replace(year=2026)

                rev = CarReview(
                    model_id=model_obj.id,
                    source_id=src_obj.id,
                    source_url=source_url,
                    rating=rating,
                    review_title=title,
                    review_text=review_text,
                    author=author,
                    review_date=review_date,
                    pros=pros_str,
                    cons=cons_str,
                    variant_tested=variant,
                    content_hash=h,
                    is_processed=False,
                    scraped_at=scraped,
                )
                session.add(rev)
                inserted += 1

    session.commit()
    print(f"    Inserted {inserted} car reviews")


def seed_listings(session, brand_model_map: dict, source_map: dict):
    """Seed ~300 listings for new brands with full detail."""
    print("  Seeding car listings...")
    listing_sources = ["AutoScout24", "Mobile.de"]
    source_objs = {s: source_map[s] for s in listing_sources if s in source_map}
    if not source_objs:
        print("    Warning: no listing sources found")
        return

    dealers = [
        "AutoHaus Müller", "Premium Cars London", "Elite Motors Paris",
        "Nordic Auto Stockholm", "Iberia Cars Madrid", "Amsterdam Auto Centre",
        "Milan Prestige Cars", "Vienna Motor Group", "Brussels Auto Park",
        "Warsaw Premium Autos", "Geneva Auto Gallery", "Copenhagen Cars",
    ]

    inserted = 0
    for brand_name, models in brand_model_map.items():
        for model_name, model_obj in models.items():
            listings_per_model = random.randint(6, 12)
            for _ in range(listings_per_model):
                city, country, currency = random.choice(EUROPEAN_CITIES)
                src_name = random.choice(list(source_objs.keys()))
                src_obj = source_objs[src_name]
                domain = src_obj.base_url.replace("https://www.", "")

                base_price = float(model_obj.msrp_eur or random.randint(25000, 120000))
                year_factor = random.uniform(0.65, 1.05)
                mileage = random.randint(0, 120000)
                mileage_factor = max(0.6, 1.0 - mileage / 300000)
                price = round(base_price * year_factor * mileage_factor * random.uniform(0.92, 1.08), -2)

                listing_year = random.choice([2021, 2022, 2023, 2024])
                fuel_type = FUEL_TYPES.get(model_obj.engine_type or "Petrol", "Petrol")
                color = random.choice(COLORS)
                transmission = model_obj.transmission or random.choice(["Automatic", "Manual"])
                trim_level = model_obj.trim_level

                slug = model_name.lower().replace(" ", "-")
                listing_id = random.randint(10000000, 99999999)
                url = f"{src_obj.base_url}/lst/{brand_name.lower()}/{slug}/{listing_id}"

                h = sha256(f"listing|{url}|{color}|{mileage}")
                if session.query(CarListing).filter(CarListing.listing_url == url).first():
                    continue

                listed_at = rand_date(180, 1)
                listing = CarListing(
                    model_id=model_obj.id,
                    source_id=src_obj.id,
                    listing_url=url,
                    dealer_name=random.choice(dealers),
                    listed_price=price,
                    currency=currency,
                    mileage_km=mileage,
                    city=city,
                    country=country,
                    listed_at=listed_at,
                    is_active=True,
                    fuel_type=fuel_type,
                    transmission=transmission,
                    color=color,
                    trim_level=trim_level,
                    listing_year=listing_year,
                )
                session.add(listing)
                inserted += 1

    session.commit()
    print(f"    Inserted {inserted} listings")


def seed_articles(session, source_map: dict):
    """Seed 90+ articles across 5 categories from 3 publications."""
    print("  Seeding market trend articles...")
    inserted = 0

    article_sources = {s: source_map[s] for s in ["Reuters", "Bloomberg", "Automotive News"] if s in source_map}
    if not article_sources:
        print("    Warning: no article sources found, creating them...")
        for s in SOURCES:
            if s["name"] in ["Reuters", "Bloomberg", "Automotive News"]:
                source_map[s["name"]] = get_or_create_source(session, s["name"], s["url"], s["reliability"])
        article_sources = {s: source_map[s] for s in ["Reuters", "Bloomberg", "Automotive News"] if s in source_map}

    ev_brands = ["Tesla", "BMW", "Volkswagen", "Hyundai", "Kia", "Porsche", "Volvo", "Nissan", "Renault"]
    mfr_brands = ["Toyota", "BMW", "Ford", "Volkswagen", "Mercedes", "Stellantis", "GM", "Hyundai Group"]

    for category, articles in ARTICLE_CATEGORIES.items():
        for pub_name, title_tmpl, region in articles:
            for iteration in range(random.randint(1, 2)):
                if pub_name not in article_sources:
                    continue
                src_obj = article_sources[pub_name]
                domain = src_obj.base_url.replace("https://www.", "").replace("https://", "")
                authors = ARTICLE_AUTHORS.get(pub_name, ["Staff Reporter"])
                author = random.choice(authors)

                # Fill template variables
                title = title_tmpl.format(
                    pct=random.randint(12, 45),
                    brand=random.choice(ev_brands if category == "EV" else mfr_brands),
                    model=random.choice(["EV Plus", "Electric Pro", "e-Series", "Charge"]),
                    range=random.randint(450, 750),
                    year=random.choice([2025, 2026, 2027]),
                    bn=random.randint(2, 15),
                    jobs=random.randint(3, 20),
                    region=region,
                )

                slug = title.lower()[:60].replace(" ", "-").replace(",", "").replace(":", "").replace("'", "")
                slug = "".join(c for c in slug if c.isalnum() or c == "-")
                pub_date = rand_date(730, 1)
                article_id = random.randint(1000000, 9999999)
                url = f"{src_obj.base_url}/articles/{category.lower()}/{slug}-{article_id}"

                h = sha256(f"article|{url}|{title}|{category}")
                if session.query(MarketTrendArticle).filter(
                    MarketTrendArticle.content_hash == h
                ).first():
                    continue
                if session.query(MarketTrendArticle).filter(
                    MarketTrendArticle.source_url == url
                ).first():
                    continue

                body = (
                    f"{title}. {pub_name} — {author} reports that industry observers have noted "
                    f"significant developments in the {category.lower()} sector. "
                    f"Market analysts confirm the trend continues to accelerate heading into "
                    f"{'Q' + str(random.randint(1,4))} {pub_date.year}. "
                    f"Stakeholders across the automotive value chain are responding with "
                    f"increased investment and strategic repositioning. Regulatory bodies "
                    f"in {region} continue to shape the trajectory of these developments. "
                    f"Further details and quarterly data are expected in upcoming earnings calls "
                    f"and industry conferences. The shift is expected to have lasting implications "
                    f"for both legacy OEMs and new market entrants through {pub_date.year + 2}."
                )

                art = MarketTrendArticle(
                    source_id=src_obj.id,
                    title=title,
                    source_url=url,
                    author=author,
                    publication_date=pub_date,
                    body_text=body,
                    category=category,
                    region=region,
                    content_hash=h,
                    is_processed=False,
                )
                session.add(art)
                inserted += 1

    session.commit()
    print(f"    Inserted {inserted} articles")


def seed_insurance_reviews(session, source_map: dict):
    """Seed 150 more insurance reviews."""
    print("  Seeding additional insurance reviews...")
    src = source_map.get("Trustpilot")
    if not src:
        src = get_or_create_source(session, "Trustpilot", "https://www.trustpilot.com", 0.82)

    insurers = [
        "Admiral", "Direct Line", "Aviva", "AXA", "Allianz",
        "Zurich Insurance", "Generali", "Axa XL", "Intact Insurance", "RSA Insurance",
    ]
    review_texts = [
        "Really competitive premium for the level of cover offered. Claims process was smoother than expected.",
        "Had to make a claim after a minor accident and the team was professional and helpful throughout.",
        "Online quote was easy and the price came in well under what other insurers offered for the same cover.",
        "Renewal price jumped significantly. Loyalty clearly isn't rewarded. Will shop around next year.",
        "Called customer service three times about the same issue. Eventually resolved but very frustrating.",
        "Excellent app — can manage your policy, upload documents and track claims all in one place.",
        "Payout was fair and prompt. No arguments about the repair estimate. Very satisfied.",
        "The telematics box installation was straightforward and the black box discount was worthwhile.",
        "Annual premium increased 18% with no claims. Switched to a competitor for a much better deal.",
        "Friendly staff and clear policy documentation. Felt properly covered and understood what I was getting.",
        "Young driver premiums are outrageous regardless of provider, but this was slightly more reasonable.",
        "Claims assessed fairly and quickly. Repair was authorised within 48 hours. Really good experience.",
    ]
    inserted = 0
    for insurer_name in insurers:
        co = session.query(InsuranceCompany).filter(InsuranceCompany.name == insurer_name).first()
        if not co:
            co = InsuranceCompany(name=insurer_name, country="Europe", is_active=True)
            session.add(co)
            session.flush()

        for _ in range(15):
            rating = round(min(5.0, max(1.0, random.gauss(3.6, 0.8))), 1)
            review_text = random.choice(review_texts)
            url_id = random.randint(1000000, 9999999)
            url = f"https://www.trustpilot.com/reviews/{insurer_name.lower().replace(' ', '-')}/{url_id}"
            h = sha256(f"ins_review|{url}|{insurer_name}|{review_text[:40]}")

            if session.query(InsuranceReview).filter(InsuranceReview.content_hash == h).first():
                continue

            scraped = rand_dt(400, 5)
            yr = scraped.year
            if yr < 2024: scraped = scraped.replace(year=2024)

            rev = InsuranceReview(
                company_id=co.id,
                source_id=src.id,
                source_url=url,
                rating=rating,
                review_title=f"{insurer_name} Car Insurance Review",
                review_text=review_text,
                author=None,
                review_date=rand_date(400, 5),
                content_hash=h,
                is_processed=False,
                scraped_at=scraped,
            )
            session.add(rev)
            inserted += 1

    session.commit()
    print(f"    Inserted {inserted} insurance reviews")


def seed_more_competitor_pricing(session, source_map: dict):
    """Seed 80 more pricing records."""
    print("  Seeding additional competitor pricing...")
    src = source_map.get("Trustpilot")  # fallback source
    insurers_pricing = [
        ("Admiral", 480, 620, "Comprehensive", "UK"),
        ("Direct Line", 510, 680, "Comprehensive", "UK"),
        ("Aviva", 550, 720, "Comprehensive", "UK"),
        ("AXA", 600, 800, "Comprehensive", "France"),
        ("Allianz", 580, 760, "Comprehensive", "Germany"),
        ("Zurich Insurance", 620, 820, "Comprehensive", "Switzerland"),
        ("Generali", 500, 680, "Comprehensive", "Italy"),
        ("Admiral", 280, 380, "Third Party Only", "UK"),
        ("Direct Line", 320, 420, "Third Party Fire & Theft", "UK"),
        ("Aviva", 580, 750, "Fully Comprehensive", "UK"),
        ("AXA", 450, 600, "Liability Only", "France"),
        ("Allianz", 480, 640, "Third Party", "Germany"),
    ]
    inserted = 0
    for insurer_name, price_lo, price_hi, cov_type, region in insurers_pricing:
        co = session.query(InsuranceCompany).filter(InsuranceCompany.name == insurer_name).first()
        if not co:
            co = InsuranceCompany(name=insurer_name, country="Europe", is_active=True)
            session.add(co)
            session.flush()

        for i in range(6):
            snap_date = date(2025, random.randint(1, 12), 1)
            price = round(random.uniform(price_lo, price_hi), 2)
            cp = CompetitorPricing(
                company_id=co.id,
                price=price,
                currency="GBP" if region == "UK" else ("CHF" if region == "Switzerland" else "EUR"),
                coverage_type=cov_type,
                region=region,
                snapshot_date=snap_date,
            )
            session.add(cp)
            inserted += 1

    session.commit()
    print(f"    Inserted {inserted} competitor pricing records")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=== Phase 2 Enrichment Seed ===\n")
    with get_db_session() as session:
        # Build source map first
        print("Loading sources...")
        source_map = {}
        for s in SOURCES:
            source_map[s["name"]] = get_or_create_source(session, s["name"], s["url"], s["reliability"])
        session.commit()

        # 1. Update existing model specs
        update_existing_model_specs(session)
        session.commit()

        # 2. New brands + models
        brand_model_map = seed_new_brands_and_models(session)

        # 3. Reviews for new brands
        seed_car_reviews(session, brand_model_map, source_map)

        # 4. Listings for new brands
        seed_listings(session, brand_model_map, source_map)

        # 5. Articles with categories
        seed_articles(session, source_map)

        # 6. Insurance reviews
        seed_insurance_reviews(session, source_map)

        # 7. More pricing records
        seed_more_competitor_pricing(session, source_map)

    # Final counts
    print("\n=== Final Record Counts ===")
    with get_db_session() as session:
        for label, query in [
            ("Brands",             "SELECT COUNT(*) FROM car_brands WHERE deleted_at IS NULL"),
            ("Models",             "SELECT COUNT(*) FROM car_models WHERE deleted_at IS NULL"),
            ("Car Reviews",        "SELECT COUNT(*) FROM car_reviews"),
            ("Insurance Reviews",  "SELECT COUNT(*) FROM insurance_reviews"),
            ("Listings",           "SELECT COUNT(*) FROM car_listings"),
            ("Articles",           "SELECT COUNT(*) FROM market_trend_articles"),
            ("Competitor Pricing", "SELECT COUNT(*) FROM competitor_pricings"),
            ("Models with HP",     "SELECT COUNT(*) FROM car_models WHERE horsepower_hp IS NOT NULL"),
            ("Models with EV range","SELECT COUNT(*) FROM car_models WHERE range_km IS NOT NULL"),
            ("Listings with color","SELECT COUNT(*) FROM car_listings WHERE color IS NOT NULL"),
            ("Articles with cat",  "SELECT COUNT(*) FROM market_trend_articles WHERE category IS NOT NULL"),
        ]:
            count = session.execute(text(query)).scalar()
            print(f"  {label:<28} {count:>6}")


if __name__ == "__main__":
    main()
