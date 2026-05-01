// Realistic AI-summary fixture for dev-mode verification of the docx export.
// Mirrors the shape, tone, and markdown conventions produced by the live
// /api/ai-summary/stream endpoint for the query
//   "impact of climate change on food security"
// against the UN Humanitarian Evaluation Reports dataset. Used only when
// REACT_APP_DEV_FIXTURES=true — see SearchTabContent wiring.

export const AI_SUMMARY_FIXTURE = `## Impact of Climate Change on Food Security

### General Impact on Food Security and Agriculture

Climate change significantly affects food security by disrupting agricultural productivity through changing rainfall patterns, increased frequency of extreme weather events such as droughts and floods, and altering the geographical distribution of pests and diseases. Evaluations across UN agencies consistently find that smallholder farmers, pastoralists, and fishing communities bear the brunt of these shifts, with women and children disproportionately affected.

### Key Vulnerabilities in Evaluated Programmes

- **Bangladesh** — Rising sea levels and saline intrusion are reducing the productivity of rice and vegetable systems on which a majority of poor rural households depend.
- **Sahel & East Africa** — Recurrent droughts have compressed the window for rain-fed cropping and driven pastoralist displacement.
- **Pacific SIDS** — Tropical cyclones increasingly damage subsistence gardens and inshore fisheries within a single growing season.

### Programmatic Responses Observed

1. Climate-smart agriculture (drought-tolerant seeds, water-efficient irrigation, agroforestry).
2. Anticipatory cash transfers triggered by meteorological indicators.
3. Diversification of livelihoods away from climate-exposed value chains.
4. Integration of nutrition-sensitive approaches into resilience programming.

### Recommendations from the Evidence Base

Evaluations recommend (a) stronger linkage between early-warning systems and social protection, (b) longer programme cycles to match ecosystem recovery horizons, and (c) more systematic inclusion of women's land-tenure rights in adaptation planning. Evidence on the cost-effectiveness of insurance-based instruments remains mixed.
`;
