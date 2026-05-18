"""Insert real professional events into market_trend_articles."""
import hashlib
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from database.connection import get_db_session
from database.models import MarketTrendArticle

EVENTS = [
    # Upcoming
    dict(
        title="Epicor Insights 2026",
        publication_date=date(2026, 5, 18),
        source_url="https://insights.epicor.com",
        category="erp",
        region="US",
        body_text="Epicor Insights is the annual user conference for Epicor ERP customers and partners. Covers manufacturing, distribution, automotive aftermarket, and dealer management systems. Audience: ERP practitioners, IT leaders, operations managers, and C-suite from industrial and automotive companies. Topics: Epicor Kinetic, digital transformation, automation, cloud ERP, supply chain, SAP migration. Location: Nashville, TN, May 18-21 2026.",
        tags=["epicor", "erp", "conference"],
    ),
    dict(
        title="TUG Connects 2026 — Infor M3 User Group Conference",
        publication_date=date(2026, 5, 18),
        source_url="https://www.tug.org",
        category="erp",
        region="US",
        body_text="TUG Connects is the annual conference for Infor M3 and CloudSuite users. Focus on ERP optimization, manufacturing, distribution. Audience: ERP practitioners, IT directors, operations teams. Themes include digital transformation, cloud ERP, SAP alternatives. Location: Nashville, TN, May 18-21 2026.",
        tags=["infor", "erp", "conference"],
    ),
    dict(
        title="Fenabrave Congress 2026 — Latin America Auto Dealer Forum",
        publication_date=date(2026, 8, 17),
        source_url="https://www.fenabrave.org.br",
        category="automotive",
        region="Global",
        body_text="Fenabrave Congress is Brazil and Latin Americas largest automotive dealer convention. Covers dealer management systems, ERP for dealerships, vehicle financing, fleet management, and automotive retail trends. Audience: automotive dealer principals, fleet managers, concessionnaire executives. Location: Sao Paulo, Brazil, Aug 17-19 2026.",
        tags=["fenabrave", "automotive", "dealer"],
    ),
    dict(
        title="P21WWUG CONNECT — Epicor Prophet 21 User Conference",
        publication_date=date(2026, 8, 16),
        source_url="https://www.p21wwug.org",
        category="erp",
        region="US",
        body_text="P21WWUG CONNECT is the annual conference for Epicor Prophet 21 users in distribution. Focus on ERP best practices, digital transformation, automation of wholesale distribution. Audience: ERP practitioners, CIO, distribution executives. Location: Orlando, FL, Aug 16-19 2026.",
        tags=["epicor", "erp", "distribution"],
    ),
    dict(
        title="Community Summit North America 2026 — Microsoft Dynamics User Conference",
        publication_date=date(2026, 10, 11),
        source_url="https://www.summitna.com",
        category="erp",
        region="US",
        body_text="Community Summit North America is the largest Microsoft Dynamics user conference globally. Covers Dynamics 365, Business Central, Finance and Operations, Power Platform, CRM. Focus on ERP implementation, digital transformation, Microsoft cloud. Audience: Microsoft Dynamics users, ERP practitioners, consultants, IT directors, CIO, CTO. Location: Nashville, TN, Oct 11-15 2026.",
        tags=["microsoft", "dynamics", "erp"],
    ),
    dict(
        title="TechCrunch Disrupt 2026",
        publication_date=date(2026, 10, 13),
        source_url="https://techcrunch.com/events/tc-disrupt-2026",
        category="startup",
        region="US",
        body_text="TechCrunch Disrupt is the flagship startup and venture capital conference. Features startup pitches, VC panels, and discussions on AI, insurtech, fintech, and enterprise software. Audience: startup founders, investors, VC, entrepreneurs. Location: San Francisco, CA, Oct 13-15 2026.",
        tags=["techcrunch", "startup", "vc"],
    ),
    dict(
        title="AM Live 2026 — Automotive Management Live",
        publication_date=date(2026, 11, 11),
        source_url="https://www.am-live.co.uk",
        category="automotive",
        region="EU",
        body_text="AM Live is the UK flagship event for automotive retail professionals. Covers dealer management systems, ERP for dealerships, used car market trends, aftersales, and digital retail. Audience: automotive dealer principals, automotive professionals, fleet managers, concessionnaire executives. Location: Birmingham, UK, Nov 11 2026.",
        tags=["automotive", "dealer", "uk"],
    ),
    dict(
        title="Acumatica Summit 2027",
        publication_date=date(2027, 1, 24),
        source_url="https://www.acumatica.com/acumatica-summit",
        category="erp",
        region="US",
        body_text="Acumatica Summit is the annual user conference for Acumatica cloud ERP. Topics include cloud ERP, digital transformation, manufacturing, distribution, and agentic AI in enterprise systems. Audience: ERP practitioners, IT directors, CTO, operations executives. Location: Seattle, WA, Jan 24-27 2027.",
        tags=["acumatica", "erp", "cloud"],
    ),
    # Recently past
    dict(
        title="SAP Sapphire & ASUG Annual Conference 2026",
        publication_date=date(2026, 5, 11),
        source_url="https://www.sap.com/events/sapphire.html",
        category="erp",
        region="US",
        body_text="SAP Sapphire is the flagship SAP conference bringing together customers, partners, and industry leaders. Covers SAP S/4HANA, cloud ERP, RISE with SAP, AI integration, automotive industry solutions, and insurance technology. Audience: ERP practitioners, CIO, CTO, IT directors. Location: Orlando, FL, May 11-13 2026.",
        tags=["sap", "erp", "conference"],
    ),
    dict(
        title="Insurance Innovators USA 2026",
        publication_date=date(2026, 5, 11),
        source_url="https://insurance-innovators.com/usa",
        category="insurance",
        region="US",
        body_text="Insurance Innovators USA brings together senior executives from US insurance carriers, reinsurers, and insurtechs. Topics include claims automation, underwriting transformation, insurtech, digital distribution, and AI in insurance. Audience: insurance leaders, CIO of insurers, underwriting executives, claims directors. Location: Nashville, TN, May 11-12 2026.",
        tags=["insurance", "insurtech", "conference"],
    ),
    dict(
        title="DynamicsCon LIVE 2026 — Microsoft Dynamics Community Conference",
        publication_date=date(2026, 5, 12),
        source_url="https://dynamicscon.com",
        category="erp",
        region="US",
        body_text="DynamicsCon LIVE is a community-led Microsoft Dynamics conference covering Dynamics 365, Business Central, Finance and Supply Chain. Focus on ERP best practices, digital transformation, automation. Audience: ERP practitioners, Microsoft Dynamics users, consultants, IT teams. Location: Las Vegas, NV, May 12-15 2026.",
        tags=["microsoft", "dynamics", "erp"],
    ),
    dict(
        title="Insurtech Insights Europe 2026",
        publication_date=date(2026, 3, 18),
        source_url="https://www.insurtechinsights.com/europe",
        category="insurance",
        region="EU",
        body_text="Insurtech Insights Europe is the leading insurtech conference in Europe. Covers digital insurance, claims automation, underwriting innovation, AI in insurance, telematics, and connected car insurance. Audience: insurance leaders, insurtech founders, VC investors, underwriting executives. Location: London, UK, March 18 2026.",
        tags=["insurance", "insurtech", "europe"],
    ),
    dict(
        title="Insurance Leaders Technology Forum 2026 — Datos Insights",
        publication_date=date(2026, 4, 8),
        source_url="https://datos-insights.com/events/insurance-technology-forum",
        category="insurance",
        region="US",
        body_text="The Insurance Leaders Technology Forum by Datos Insights brings together CIO and technology executives from leading P&C and life insurance carriers. Topics include core system modernization, cloud ERP for insurers, claims digital transformation, underwriting AI. Audience: CIO of insurers, insurance technology leaders, C-suite executives. Virtual online event, April 2026.",
        tags=["insurance", "technology", "virtual"],
    ),
]


def main():
    inserted = 0
    skipped = 0
    with get_db_session() as s:
        for ev in EVENTS:
            h = hashlib.sha256((ev["title"] + str(ev["publication_date"])).encode()).hexdigest()
            exists = s.query(MarketTrendArticle).filter_by(content_hash=h).first()
            if exists:
                skipped += 1
                print(f"  SKIP (exists): {ev['title']}")
                continue
            article = MarketTrendArticle(
                title=ev["title"],
                publication_date=ev["publication_date"],
                source_url=ev["source_url"],
                category=ev["category"],
                region=ev["region"],
                body_text=ev["body_text"],
                tags=ev["tags"],
                data_origin="seeded",
                content_hash=h,
            )
            s.add(article)
            inserted += 1
            print(f"  INSERT: [{ev['publication_date']}] {ev['title']}")
        s.commit()
    print(f"\nDone: {inserted} inserted, {skipped} skipped")


if __name__ == "__main__":
    main()
