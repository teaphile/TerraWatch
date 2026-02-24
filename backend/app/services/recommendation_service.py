"""AI-powered recommendation service.

Generates agricultural, disaster preparedness, and environmental
restoration recommendations based on soil and risk analysis.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating AI-powered recommendations.

    Provides agricultural, disaster preparedness, and environmental
    restoration suggestions based on analysis results.
    """

    # Crop suitability database
    CROP_DATABASE = {
        "rice": {"ph_range": (5.5, 7.0), "moisture": "high", "texture": ["Clay", "Silty Clay", "Clay Loam"], "temp_range": (20, 35)},
        "wheat": {"ph_range": (6.0, 7.5), "moisture": "moderate", "texture": ["Loam", "Silt Loam", "Clay Loam"], "temp_range": (10, 25)},
        "corn": {"ph_range": (5.8, 7.0), "moisture": "moderate", "texture": ["Loam", "Sandy Loam", "Silt Loam"], "temp_range": (18, 32)},
        "soybean": {"ph_range": (6.0, 7.0), "moisture": "moderate", "texture": ["Loam", "Silt Loam", "Clay Loam"], "temp_range": (15, 30)},
        "potato": {"ph_range": (5.0, 6.5), "moisture": "moderate", "texture": ["Sandy Loam", "Loam"], "temp_range": (10, 25)},
        "tomato": {"ph_range": (6.0, 6.8), "moisture": "moderate", "texture": ["Loam", "Sandy Loam"], "temp_range": (18, 30)},
        "cotton": {"ph_range": (6.0, 8.0), "moisture": "low", "texture": ["Loam", "Sandy Loam", "Sandy Clay Loam"], "temp_range": (20, 35)},
        "sugarcane": {"ph_range": (5.5, 7.5), "moisture": "high", "texture": ["Loam", "Clay Loam", "Silt Loam"], "temp_range": (22, 35)},
        "cassava": {"ph_range": (5.5, 7.0), "moisture": "low", "texture": ["Sandy Loam", "Loam"], "temp_range": (22, 32)},
        "barley": {"ph_range": (6.0, 8.0), "moisture": "low", "texture": ["Loam", "Silt Loam"], "temp_range": (8, 22)},
        "millet": {"ph_range": (5.5, 7.5), "moisture": "low", "texture": ["Sandy Loam", "Loam", "Sand"], "temp_range": (20, 35)},
        "coffee": {"ph_range": (5.0, 6.5), "moisture": "moderate", "texture": ["Loam", "Clay Loam"], "temp_range": (15, 25)},
    }

    def get_agricultural_recommendations(
        self,
        soil_analysis: Dict[str, Any],
        climate: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate agricultural recommendations based on soil analysis.

        Args:
            soil_analysis: Complete soil analysis result.
            climate: Climate data (temperature, precipitation).

        Returns:
            Recommendations for crops, fertilizers, irrigation, and amendments.
        """
        props = soil_analysis.get("soil_properties", {})
        ph = props.get("ph", {}).get("value", 6.5)
        oc = props.get("organic_carbon_pct", {}).get("value", 1.5)
        nitrogen = props.get("nitrogen_pct", {}).get("value", 0.15)
        texture = props.get("texture", {}).get("classification", "Loam")
        moisture = props.get("moisture_pct", {}).get("value", 30)

        temp = 20
        if climate:
            temp = climate.get("mean_annual_temp_c", 20)

        # Crop recommendations
        suitable_crops = self._find_suitable_crops(ph, texture, moisture, temp)

        # Fertilizer recommendations
        fertilizer = self._recommend_fertilizer(ph, oc, nitrogen, texture)

        # Irrigation recommendations
        irrigation = self._recommend_irrigation(moisture, texture, temp)

        # Soil amendments
        amendments = self._recommend_amendments(ph, oc, texture)

        return {
            "suitable_crops": suitable_crops,
            "fertilizer_recommendations": fertilizer,
            "irrigation_schedule": irrigation,
            "soil_amendments": amendments,
            "summary": self._generate_summary(
                suitable_crops, fertilizer, irrigation, amendments
            ),
        }

    def get_disaster_recommendations(
        self, risk_assessment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate disaster preparedness recommendations.

        Args:
            risk_assessment: Multi-hazard risk assessment result.

        Returns:
            Preparedness, mitigation, and response recommendations.
        """
        risks = risk_assessment.get("risks", {})
        recommendations = []

        # Landslide recommendations
        ls = risks.get("landslide", {})
        if ls.get("probability", 0) > 0.3:
            recommendations.extend(self._landslide_recommendations(ls))

        # Flood recommendations
        fl = risks.get("flood", {})
        if fl.get("probability", 0) > 0.3:
            recommendations.extend(self._flood_recommendations(fl))

        # Liquefaction recommendations
        liq = risks.get("liquefaction", {})
        if liq.get("probability_given_m7", 0) > 0.3:
            recommendations.extend(self._liquefaction_recommendations(liq))

        # Wildfire recommendations
        wf = risks.get("wildfire", {})
        if wf.get("probability", 0) > 0.3:
            recommendations.extend(self._wildfire_recommendations(wf))

        if not recommendations:
            recommendations.append({
                "category": "general",
                "priority": "low",
                "title": "Low Risk Area",
                "description": "This area has relatively low disaster risk. Maintain standard preparedness measures.",
                "actions": [
                    "Keep emergency kit with supplies for 72 hours",
                    "Know your local emergency contacts and evacuation routes",
                    "Stay informed about weather alerts",
                ],
            })

        return {
            "recommendations": recommendations,
            "overall_preparedness_level": self._preparedness_level(
                risk_assessment.get("composite_risk_score", 0)
            ),
        }

    def get_environmental_recommendations(
        self,
        soil_analysis: Dict[str, Any],
        risk_assessment: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate environmental restoration suggestions.

        Args:
            soil_analysis: Soil analysis result.
            risk_assessment: Optional risk assessment.

        Returns:
            Reforestation, wetland, and remediation recommendations.
        """
        props = soil_analysis.get("soil_properties", {})
        carbon = soil_analysis.get("carbon_sequestration", {})
        health = soil_analysis.get("health_index", {})
        metadata = soil_analysis.get("metadata", {})

        recommendations = []

        # Reforestation suitability
        if metadata.get("ndvi", 0.5) < 0.4:
            recommendations.append({
                "category": "reforestation",
                "suitability": "High",
                "description": "This area has low vegetation cover and would benefit from reforestation.",
                "suggested_species": self._suggest_tree_species(
                    props, soil_analysis.get("climate", {}),
                ),
                "expected_carbon_gain_tons_ha": round(
                    carbon.get("potential_stock_tons_ha", 50) -
                    carbon.get("current_stock_tons_ha", 30), 1
                ),
            })

        # Soil carbon improvement
        if carbon.get("improvement_potential_pct", 0) > 30:
            recommendations.append({
                "category": "carbon_sequestration",
                "description": "Significant potential to increase soil carbon storage.",
                "practices": [
                    "No-till farming to reduce carbon loss",
                    "Cover cropping to add organic matter",
                    "Composting and organic amendments",
                    "Agroforestry integration",
                ],
                "potential_carbon_credit_tons_yr": round(
                    (carbon.get("potential_stock_tons_ha", 50) -
                     carbon.get("current_stock_tons_ha", 30)) * 0.05, 2
                ),
            })

        # Soil health improvement
        if health.get("score", 100) < 60:
            recommendations.append({
                "category": "soil_remediation",
                "description": "Soil health needs improvement.",
                "strategies": self._remediation_strategies(props, health),
            })

        return {"recommendations": recommendations}

    def _find_suitable_crops(
        self, ph: float, texture: str, moisture: float, temp: float
    ) -> List[Dict[str, Any]]:
        """Find suitable crops for given soil conditions."""
        suitable = []

        for crop, req in self.CROP_DATABASE.items():
            score = 0

            # pH suitability
            ph_lo, ph_hi = req["ph_range"]
            if ph_lo <= ph <= ph_hi:
                score += 3
            elif ph_lo - 0.5 <= ph <= ph_hi + 0.5:
                score += 1

            # Temperature
            t_lo, t_hi = req["temp_range"]
            if t_lo <= temp <= t_hi:
                score += 2
            elif t_lo - 5 <= temp <= t_hi + 5:
                score += 1

            # Texture match
            if texture in req["texture"]:
                score += 2

            # Moisture match
            moisture_level = "low" if moisture < 20 else "moderate" if moisture < 40 else "high"
            if moisture_level == req["moisture"]:
                score += 1

            if score >= 4:
                suitable.append({
                    "crop": crop.replace("_", " ").title(),
                    "suitability_score": score,
                    "suitability": "Excellent" if score >= 7 else "Good" if score >= 5 else "Fair",
                })

        suitable.sort(key=lambda x: x["suitability_score"], reverse=True)
        return suitable[:6]

    def _recommend_fertilizer(
        self, ph: float, oc: float, nitrogen: float, texture: str
    ) -> List[Dict[str, str]]:
        """Recommend fertilizers based on soil deficiencies."""
        recs = []

        if nitrogen < 0.1:
            recs.append({
                "nutrient": "Nitrogen",
                "status": "Deficient",
                "recommendation": "Apply nitrogen-rich fertilizer (urea, ammonium nitrate) at 120-150 kg N/ha",
                "organic_alternative": "Green manure crops, legume rotation, or compost",
            })
        elif nitrogen < 0.2:
            recs.append({
                "nutrient": "Nitrogen",
                "status": "Low",
                "recommendation": "Apply moderate nitrogen at 80-100 kg N/ha",
                "organic_alternative": "Cover crops and crop residue incorporation",
            })

        if oc < 1.0:
            recs.append({
                "nutrient": "Organic Matter",
                "status": "Very Low",
                "recommendation": "Add 5-10 tons/ha of compost or well-rotted manure",
                "organic_alternative": "Mulching, cover crops, and reduced tillage",
            })

        if ph < 5.5:
            recs.append({
                "nutrient": "Lime",
                "status": "Needed",
                "recommendation": f"Apply agricultural lime to raise pH from {ph} to 6.0-6.5",
                "organic_alternative": "Wood ash or dolomite lime",
            })
        elif ph > 8.0:
            recs.append({
                "nutrient": "Sulfur",
                "status": "Needed",
                "recommendation": f"Apply elemental sulfur to lower pH from {ph} to 7.0-7.5",
                "organic_alternative": "Organic mulch and acidifying amendments",
            })

        if not recs:
            recs.append({
                "nutrient": "General",
                "status": "Adequate",
                "recommendation": "Soil nutrient levels are adequate. Apply balanced NPK (10-10-10) for maintenance.",
                "organic_alternative": "Regular compost application",
            })

        return recs

    def _recommend_irrigation(
        self, moisture: float, texture: str, temp: float
    ) -> Dict[str, Any]:
        """Recommend irrigation schedule."""
        # Water holding capacity by texture
        whc = {
            "Sand": "Low", "Loamy Sand": "Low", "Sandy Loam": "Medium-Low",
            "Loam": "Medium", "Silt Loam": "Medium-High", "Silt": "Medium-High",
            "Clay Loam": "Medium-High", "Clay": "High",
        }
        capacity = whc.get(texture, "Medium")

        if moisture < 15:
            frequency = "Daily to every 2 days"
            depth = "25-30mm per irrigation"
            urgency = "High"
        elif moisture < 25:
            frequency = "Every 2-3 days"
            depth = "20-25mm per irrigation"
            urgency = "Moderate"
        elif moisture < 40:
            frequency = "Every 3-5 days"
            depth = "15-20mm per irrigation"
            urgency = "Low"
        else:
            frequency = "Every 5-7 days or as needed"
            depth = "10-15mm per irrigation"
            urgency = "Very Low"

        return {
            "water_holding_capacity": capacity,
            "current_moisture_pct": round(moisture, 1),
            "irrigation_frequency": frequency,
            "irrigation_depth": depth,
            "urgency": urgency,
            "method": "drip" if temp > 30 else "sprinkler",
            "best_time": "Early morning (6-9 AM) or late evening",
        }

    def _recommend_amendments(
        self, ph: float, oc: float, texture: str
    ) -> List[Dict[str, str]]:
        """Recommend soil amendments."""
        amendments = []

        if oc < 2.0:
            amendments.append({
                "amendment": "Organic Compost",
                "purpose": "Increase organic matter and soil biology",
                "application_rate": "5-10 tons/ha annually",
            })

        if texture in ("Sand", "Loamy Sand", "Sandy Loam"):
            amendments.append({
                "amendment": "Biochar",
                "purpose": "Improve water retention and carbon storage",
                "application_rate": "2-5 tons/ha",
            })

        if texture in ("Clay", "Silty Clay", "Sandy Clay"):
            amendments.append({
                "amendment": "Gypsum",
                "purpose": "Improve soil structure and drainage",
                "application_rate": "2-4 tons/ha",
            })

        return amendments

    def _landslide_recommendations(self, risk: Dict) -> List[Dict]:
        """Generate landslide-specific recommendations."""
        return [{
            "category": "landslide",
            "priority": "high" if risk.get("probability", 0) > 0.6 else "medium",
            "title": "Landslide Risk Mitigation",
            "description": f"Landslide probability: {risk.get('probability', 0):.0%}",
            "actions": [
                "Avoid construction on steep slopes (>25°)",
                "Plant deep-rooted vegetation for slope stabilization",
                "Install proper drainage systems to reduce water infiltration",
                "Build retaining walls where necessary",
                "Monitor for signs: cracks in ground, tilting trees/poles",
                "Prepare evacuation plan for downslope areas",
            ],
        }]

    def _flood_recommendations(self, risk: Dict) -> List[Dict]:
        """Generate flood-specific recommendations."""
        return [{
            "category": "flood",
            "priority": "high" if risk.get("probability", 0) > 0.6 else "medium",
            "title": "Flood Risk Preparedness",
            "description": f"Flood probability: {risk.get('probability', 0):.0%}, "
                          f"Return period: {risk.get('return_period_years', 'N/A')} years",
            "actions": [
                "Elevate electrical systems and appliances",
                "Install flood barriers or sandbags for critical areas",
                "Ensure proper drainage and waterway maintenance",
                "Store important documents in waterproof containers",
                "Know flood evacuation routes and shelter locations",
                "Consider flood insurance if in high-risk zone",
            ],
        }]

    def _liquefaction_recommendations(self, risk: Dict) -> List[Dict]:
        """Generate liquefaction-specific recommendations."""
        return [{
            "category": "earthquake_liquefaction",
            "priority": "medium",
            "title": "Earthquake Liquefaction Risk",
            "description": f"Liquefaction susceptibility: {risk.get('susceptibility', 'N/A')}",
            "actions": [
                "Use deep foundations for new construction",
                "Improve soil density through compaction or grouting",
                "Lower groundwater table if possible",
                "Avoid placing heavy structures on susceptible soils",
                "Conduct detailed geotechnical survey before construction",
            ],
        }]

    def _wildfire_recommendations(self, risk: Dict) -> List[Dict]:
        """Generate wildfire-specific recommendations."""
        return [{
            "category": "wildfire",
            "priority": "high" if risk.get("probability", 0) > 0.6 else "medium",
            "title": "Wildfire Risk Management",
            "description": f"Wildfire probability: {risk.get('probability', 0):.0%}",
            "actions": [
                "Create defensible space: clear vegetation 30m around structures",
                "Use fire-resistant building materials",
                "Maintain fire breaks around property",
                "Keep garden and brush well-watered during dry periods",
                "Prepare evacuation plan and emergency kit",
                "Report any unattended fires immediately",
            ],
        }]

    def _preparedness_level(self, composite_score: int) -> str:
        """Determine overall preparedness recommendation level."""
        if composite_score < 20:
            return "Standard"
        elif composite_score < 40:
            return "Enhanced"
        elif composite_score < 60:
            return "Elevated"
        elif composite_score < 80:
            return "High"
        return "Maximum"

    def _suggest_tree_species(
        self, props: Dict, climate: Dict
    ) -> List[str]:
        """Suggest tree species for reforestation."""
        temp = climate.get("mean_annual_temp_c", climate.get("current_weather", {}).get("temperature_c", 20))

        if temp > 25:
            return ["Teak", "Mahogany", "Eucalyptus", "Acacia", "Bamboo"]
        elif temp > 15:
            return ["Oak", "Pine", "Maple", "Birch", "Walnut"]
        elif temp > 5:
            return ["Spruce", "Fir", "Larch", "Birch", "Alder"]
        return ["Arctic Willow", "Dwarf Birch", "Black Spruce"]

    def _remediation_strategies(
        self, props: Dict, health: Dict
    ) -> List[str]:
        """Generate soil remediation strategies."""
        strategies = []
        ph = props.get("ph", {}).get("value", 7)
        oc = props.get("organic_carbon_pct", {}).get("value", 2)

        if ph < 5.5:
            strategies.append("Apply lime to correct acidic conditions")
        elif ph > 8.0:
            strategies.append("Apply sulfur or acidifying amendments")

        if oc < 1.5:
            strategies.append("Increase organic matter through composting and cover crops")

        strategies.extend([
            "Minimize tillage to preserve soil structure",
            "Implement crop rotation to prevent nutrient depletion",
            "Use mulching to reduce erosion and retain moisture",
        ])

        return strategies

    def _generate_summary(
        self,
        crops: List[Dict],
        fertilizer: List[Dict],
        irrigation: Dict,
        amendments: List[Dict],
    ) -> str:
        """Generate a text summary of recommendations."""
        parts = []

        if crops:
            crop_names = [c["crop"] for c in crops[:3]]
            parts.append(f"Best suited crops: {', '.join(crop_names)}.")

        if any(f["status"] != "Adequate" for f in fertilizer):
            deficient = [f["nutrient"] for f in fertilizer if f["status"] in ("Deficient", "Very Low")]
            if deficient:
                parts.append(f"Soil is deficient in: {', '.join(deficient)}.")

        parts.append(f"Irrigation urgency: {irrigation['urgency']}.")

        if amendments:
            parts.append(f"Recommended amendments: {', '.join(a['amendment'] for a in amendments)}.")

        return " ".join(parts)


_service_instance: Optional[RecommendationService] = None


def get_recommendation_service() -> RecommendationService:
    """Get or create singleton recommendation service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = RecommendationService()
    return _service_instance
