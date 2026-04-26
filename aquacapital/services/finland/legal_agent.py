"""
Finnish Water Law (Vesilaki 587/2011) legal consultant agent.
Uses Claude to act as a Finnish water law specialist checking permit requirements
and construction restrictions based on SYKE flood hazard and groundwater data.

Key Vesilaki sections checked:
  Chapter 2  §2  — Prohibition of environmental harm
  Chapter 3  §2  — Groundwater abstraction permit threshold (>250 m³/day)
  Chapter 3  §4  — Groundwater protection zone restrictions
  Chapter 4  §2  — Ditch/waterway modification permits
  Chapter 5  §3  — Surface water abstraction from lakes/rivers
  Chapter 18 §2  — Water permit application requirement triggers
  EU WFD Art.4    — Non-deterioration obligation (transposed via Vesienhoidosta ja
                    merenhoidosta annettu laki 1299/2004)
"""

from __future__ import annotations

import anthropic
from fastapi import HTTPException
from config import settings

_SYSTEM_PROMPT = """You are a specialist Finnish Water Law consultant for AquaCapital.
You assess permit requirements and construction restrictions for data centre and industrial
investments under Finnish water legislation. You cite specific chapter and section numbers.

Your legal knowledge base:
- Vesilaki 587/2011 (Water Act) — primary legislation
- Ympäristönsuojelulaki 527/2014 (Environmental Protection Act)
- Maankäyttö- ja rakennuslaki 132/1999 (Land Use and Building Act)
- EU Water Framework Directive (2000/60/EC) transposed as Laki vesienhoidosta 1299/2004
- SYKE flood risk maps (Tulvavaarakartat) have legal force under Laki tulvariskien hallinnasta 620/2010

Rules you ALWAYS apply:
1. Any water abstraction > 250 m³/day requires a permit (Vesilaki Ch.3 §2)
2. Construction in a SYKE 1-in-100yr flood zone requires flood risk assessment and may need
   a derogation from the regional ELY Centre
3. Class 1A/1B groundwater areas trigger strict protection obligations (Vesilaki Ch.3 §4)
4. Data centres in groundwater protection zones require Environmental Permit
5. You never give definitive legal advice — always recommend engaging a Finnish environmental lawyer

Format your response as:
1. PERMIT REQUIREMENTS (bullet list of specific permits needed)
2. RESTRICTIONS (what is prohibited or restricted)
3. RISK FLAGS (what needs further assessment)
4. RECOMMENDED ACTIONS (concrete next steps)
5. LEGAL CITATIONS (specific Vesilaki chapters/sections)"""


def run_legal_assessment(
    lat: float,
    lon: float,
    syke_data: dict,
    facility_type: str = "data_center",
    water_abstraction_m3day: float = 300.0,
) -> str:
    """
    Run Claude as a Vesilaki legal consultant with SYKE data context.
    Returns structured legal assessment.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured.")

    flood = syke_data.get("flood_hazard", {})
    gw    = syke_data.get("groundwater", {})
    lake  = syke_data.get("lake_depth", {})

    user_prompt = f"""
Assess this proposed {facility_type} development under Finnish water law.

LOCATION: {lat}°N, {lon}°E

SYKE FLOOD HAZARD DATA:
- In 50-year flood zone:  {flood.get('in_50yr_zone', 'unknown')}
- In 100-year flood zone: {flood.get('in_100yr_zone', 'unknown')}
- In 250-year flood zone: {flood.get('in_250yr_zone', 'unknown')}
- Flood zone label: {flood.get('flood_zone_label', 'unknown')}
- Data source: {flood.get('syke_source', 'SYKE Tulvavaarakartat')}

SYKE GROUNDWATER CLASSIFICATION:
- Groundwater class: {gw.get('groundwater_class', 'None (unclassified)')}
- Area name: {gw.get('area_name', 'N/A')}
- CNDCP weight: {gw.get('class_weight', 0.3)}
- Data source: {gw.get('syke_source', 'SYKE Pohjavesialueet')}

NEAREST LAKE (for water intake):
- Lake: {lake.get('nearest_lake_name', 'N/A')}
- Max depth: {lake.get('max_depth_m', 'N/A')} m
- Heat exchange viable: {lake.get('heat_exchange_viable', False)}

FACILITY PARAMETERS:
- Type: {facility_type}
- Proposed daily water abstraction: {water_abstraction_m3day} m³/day
- Annual estimate: {water_abstraction_m3day * 365:,.0f} m³/year

Provide your full legal assessment under Vesilaki 587/2011 and related Finnish legislation.
"""

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text
    except anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"Claude API error: {exc}") from exc
