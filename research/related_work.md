# Related work and research framing

_Last reviewed: 17 November 2026. This is an initial literature map, not a systematic review._

## 1. Problem formulation: Tourist Trip Design / Orienteering

Tourist Trip Design Problems (TTDPs) combine POI selection, visit ordering, user preferences, visit durations, travel time, and opening-hour constraints. The Rahgir planning problem is therefore most naturally connected to the Orienteering Problem (OP), Team Orienteering Problem with Time Windows, and multi-objective variants—not to generic conversational question answering.

Gavalas et al. survey TTDP formulations and algorithmic approaches. Their framing emphasizes selecting preference-relevant POIs and producing an ordered itinerary while accounting for realistic attributes such as visit duration, travel distance, POI opening hours and weather. This informs Rahgir's hard feasibility constraints and itinerary-level evaluation.

Gunawan, Lau and Vansteenwegen review OP variants, including time windows and time-dependent variants, and discuss tourist trip planning as an application. Ruiz-Meza and Montoya-Torres provide a more recent systematic literature review of 102 TTDP papers (to February 2021), classifying models and solution approaches. Their review notes that TTDP is commonly modelled as OP or Team OP and that time windows are recurrent constraints. These sources support the problem class; they do not establish that Rahgir's particular formulation is novel.

## 2. Multi-objective search

Deb et al. introduce NSGA-II, an elitist non-dominated sorting genetic algorithm that uses a fast sorting mechanism and crowding-distance diversity preservation. Rahgir uses a binary genome to represent the selected subset of candidate POIs. The itinerary order is currently constrained to route-corridor progress to avoid backtracking; this is a deliberate approximation and a research limitation, not a claim to solve the unrestricted routing problem.

Zitzler et al. discuss the quantitative assessment of multi-objective approximation sets and the limitations of quality indicators. Rahgir's benchmark harness therefore records both hypervolume and inverted generational distance (IGD), using a shared reference front for small synthetic instances. A Monte-Carlo hypervolume estimate is labelled as such and uses a fixed random seed for reproducibility.

## 3. Personalised itinerary recommendation

Halder et al. study efficient itinerary recommendation via personalised POI selection and pruning, with an MCTS/reinforcement-learning approach evaluated on theme-park datasets. Gasmi et al. (2024) present multi-objective recommendation rules for tourists in an unfamiliar city. These studies reinforce that preference modelling and search-space pruning are central challenges. Rahgir's current system uses explicit preference sliders and deterministic feature scoring; it does not learn a user profile or claim collaborative-filtering performance.

Werneck et al. review POI recommendation methods, evaluation and future directions, and call attention to reproducibility and benchmark concerns. Rahgir's research plan consequently separates live map-derived observations, consented human judgements, and synthetic algorithm fixtures.

## 4. Data provenance and operational constraints

OpenStreetMap data is distributed under the Open Database License (ODbL), and attribution to OpenStreetMap and its contributors is required. Nominatim's public instance has a strict usage policy: at most one request per second, an identifying User-Agent/Referer, attribution, and no client-side autocomplete or systematic/bulk querying. Rahgir therefore calls geocoding only after explicit user submission, caches lookups, and keeps the geocoder endpoint configurable.

The public OSRM demo server is a best-effort service with limited/reasonable-use expectations; it is unsuitable as a production SLA. For production, use a contracted routing API or self-hosted routing stack. Overpass public instances are shared resources and their operators recommend caching, rate limiting and self-hosting/paid infrastructure for commercial or regular larger use.

## 5. What might be publishable—and what is not yet established

A plausible research contribution is an evaluated evidence-aware, route-corridor TTDP pipeline for Indian inter-city road journeys, with explicit provenance, uncertainty abstention for unsupported safety claims, preference-aware discovery, and a Pareto decision interface. The novelty claim must be narrowed only after a formal systematic search and direct comparison with existing TTDP/OP variants.

The current code is an initial prototype implementation. Its `category_novelty_proxy` is only the inverse frequency of a category in the retrieved route-corridor candidate set; it is not measured popularity or a validated hidden-gem label. `metadata_completeness` counts mapped OSM fields; it is not a probability of factual correctness. The safety subsystem intentionally abstains because no validated segment-level safety ground truth is connected.

## References

1. Gavalas, D., Konstantopoulos, C., Mastakas, K., & Pantziou, G. (2014). A survey on algorithmic approaches for solving tourist trip design problems. *Journal of Heuristics*, 20(3), 291–328. https://doi.org/10.1007/s10732-014-9242-5
2. Deb, K., Pratap, A., Agarwal, S., & Meyarivan, T. (2002). A fast and elitist multiobjective genetic algorithm: NSGA-II. *IEEE Transactions on Evolutionary Computation*, 6(2), 182–197. https://doi.org/10.1109/4235.996017
3. Gunawan, A., Lau, H. C., & Vansteenwegen, P. (2016). Orienteering Problem: A survey of recent variants, solution approaches and applications. *European Journal of Operational Research*, 255(2), 315–332. https://doi.org/10.1016/j.ejor.2016.04.059
4. Ruiz-Meza, J. L., & Montoya-Torres, J. R. (2022). A systematic literature review for the tourist trip design problem: Extensions, solution techniques and future research lines. *Operations Research Perspectives*, 9, 100228. https://doi.org/10.1016/j.orp.2022.100228
5. Halder, S., Lim, K. H., Chan, J., et al. (2022). Efficient itinerary recommendation via personalized POI selection and pruning. *Knowledge and Information Systems*, 64, 963–993. https://doi.org/10.1007/s10115-021-01648-3
6. Gasmi, I., Soui, M., Barhoumi, K., & Abed, M. (2024). Recommendation rules to personalize itineraries for tourists in an unfamiliar city. *Applied Soft Computing*, 150, 111084. https://doi.org/10.1016/j.asoc.2023.111084
7. Werneck, H., Silva, N., Viana, M., Pereira, A. C. M., Mourão, F., & Rocha, L. (2021). Points of Interest recommendations: Methods, evaluation, and future directions. *Information Systems*, 101, 101789. https://doi.org/10.1016/j.is.2021.101789
8. Zitzler, E., Thiele, L., Laumanns, M., Fonseca, C. M., & Grunert da Fonseca, V. (2003). Performance assessment of multiobjective optimizers: An analysis and review. *IEEE Transactions on Evolutionary Computation*, 7(2), 117–132. https://doi.org/10.1109/TEVC.2003.810758
