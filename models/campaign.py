from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Ad:
    ad_id: str
    ad_name: str
    ad_set_name: str
    campaign_name: str
    impressions: int
    reach: int
    clicks: int
    link_clicks: int
    spend: float
    results: int
    ctr: float
    cpc: float
    cpm: float
    roas: float
    frequency: float
    cost_per_result: float

    @property
    def performance_label(self) -> str:
        if self.roas >= 4.0:
            return "Excellent"
        elif self.roas >= 2.0:
            return "Goed"
        elif self.roas >= 1.0:
            return "Break-even"
        else:
            return "Ondermaats"


@dataclass
class AdSet:
    ad_set_id: str
    ad_set_name: str
    campaign_name: str
    impressions: int
    reach: int
    clicks: int
    link_clicks: int
    spend: float
    results: int
    ctr: float
    cpc: float
    cpm: float
    roas: float
    frequency: float
    cost_per_result: float
    ads: list = field(default_factory=list)


@dataclass
class Campaign:
    campaign_id: str
    campaign_name: str
    impressions: int
    reach: int
    clicks: int
    link_clicks: int
    spend: float
    results: int
    ctr: float
    cpc: float
    cpm: float
    roas: float
    frequency: float
    cost_per_result: float
    ad_sets: list = field(default_factory=list)


@dataclass
class AnalysisSummary:
    total_spend: float
    total_impressions: int
    total_reach: int
    total_clicks: int
    total_link_clicks: int
    total_results: int
    avg_ctr: float
    avg_cpc: float
    avg_cpm: float
    avg_roas: float
    avg_frequency: float
    avg_cost_per_result: float
    num_campaigns: int
    num_ad_sets: int
    num_ads: int
    campaign_type: str = "leads"  # "leads", "purchases", "awareness"
    top_ad: Optional[str] = None
    top_ad_set: Optional[str] = None
    worst_ad: Optional[str] = None
    worst_ad_set: Optional[str] = None
    has_click_data: bool = True
    campaigns: list = field(default_factory=list)

    @property
    def metric_label(self) -> str:
        if self.campaign_type == "awareness":
            return "CPM"
        elif self.campaign_type == "purchases":
            return "CPR"
        return "CPL"

    @property
    def result_label(self) -> str:
        if self.campaign_type == "purchases":
            return "Conversies"
        elif self.campaign_type == "awareness":
            return "ThruPlays"
        return "Leads"
