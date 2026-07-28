"""Original UCAT-style seed questions for UCATify.

The material in this module was written for this project. It was benchmarked
against the structure and reasoning demands of the official 2026 UCAT practice
resources without copying or paraphrasing their passages, scenarios, questions,
or distinctive fact patterns.
"""


def _mcq(stem, options, correct, explanation, difficulty):
    """Return the database's uniform five-option question tuple."""
    padded = list(options) + [""] * (5 - len(options))
    return (stem, *padded[:5], correct, explanation, difficulty)


def _vr_tfc(stem, correct, reason, difficulty="Medium"):
    labels = {
        "A": "True",
        "B": "False",
        "C": "Can't Tell",
    }
    alternatives = {
        "A": "False would require the passage to contradict the statement, while Can't Tell would require the relevant relationship to be unstated.",
        "B": "True would require the statement to agree with the passage, while Can't Tell would require no contradiction to be available.",
        "C": "True is not established by the passage, and False would require the passage to establish the opposite.",
    }
    return _mcq(
        stem,
        ["True", "False", "Can't Tell"],
        correct,
        f"{correct} ({labels[correct]}) is correct. {reason} {alternatives[correct]}",
        difficulty,
    )


VR_PASSAGE_SETS = [
    (
        "VR",
        "True / False / Can't Tell",
        "Restoring the Fenmere Peatlands",
        """For much of the twentieth century, Fenmere's peatlands were crossed by narrow drains intended to make the ground suitable for grazing. The scheme never produced the firm pasture its promoters expected, but it did lower the water table. Exposed peat reacted with oxygen and gradually released carbon that had accumulated over centuries. In dry summers, the drained surface also became vulnerable to fire.

In 2018 the local land trust began blocking selected drains with peat dams. Its first monitoring report found that water levels rose quickly beside the blocked channels, yet remained low on ridges only a short distance away. Mosses associated with wet bogs returned in some hollows, whereas grasses continued to dominate the higher ground. The trust therefore rejected the claim that blocking drains alone would restore the whole site uniformly.

The project later added shallow contour banks and reduced winter grazing. These measures slowed surface runoff, but they also created temporary pools in places used by ground-nesting birds. Volunteers worried that the pools would attract predators. A three-year bird survey recorded fewer nests beside the deepest pools, although total breeding numbers across Fenmere changed little. The researchers cautioned that the survey could not show whether predators, vegetation, or simple relocation caused the local pattern.

Farmers downstream initially feared that wetter peat would increase floods. Gauges installed on two streams instead showed that storm peaks arrived later after restoration began. Peak height fell in one stream but not the other. The trust describes this as encouraging evidence that rewetting can slow water movement, not as proof that every restored peatland will reduce downstream flooding. It plans to monitor both streams through several unusually wet and dry years before drawing a stronger conclusion.""",
        [
            _vr_tfc(
                "Water levels rose quickly beside blocked channels but remained lower on nearby ridges.",
                "A",
                "This is the contrast reported in the first monitoring results.",
            ),
            _vr_tfc(
                "The deepest pools contained more ground-nesting birds in the second survey year than in the first.",
                "C",
                "The passage reports an overall three-year pattern beside deep pools but gives no year-by-year comparison.",
                "Hard",
            ),
            _vr_tfc(
                "After restoration began, storm peaks were delayed in both monitored streams.",
                "A",
                "The passage states that gauges on the two streams recorded later storm peaks after restoration began.",
            ),
            _vr_tfc(
                "The contour banks were more effective than reduced grazing at slowing surface runoff.",
                "C",
                "The two measures were introduced together and their separate effects were not compared.",
                "Hard",
            ),
        ],
    ),
    (
        "VR",
        "Inference & Author Tone",
        "The Night Bus Trial",
        """When Northport proposed a year-long night-bus trial, the debate was framed as a choice between public safety and an expensive service that few people would use. The transport authority selected three routes connecting the city centre with districts whose late-shift workers had reported difficulty getting home. Buses ran hourly from midnight until 4 a.m. on Fridays and Saturdays. Fares matched daytime prices, while operating costs were partly met by a levy on large late-night venues.

Passenger numbers were modest during the first two months, then rose after hospitals and warehouses began including timetables in staff briefings. By the final quarter, average occupancy was 41 per cent. That figure was lower than the daytime network average but higher than the authority's minimum target of 30 per cent. Journeys were unevenly distributed: the route serving two hospitals carried nearly twice as many passengers as the route through the entertainment district.

Police recorded fewer reports of disorder at two city-centre taxi ranks during trial hours. However, the evaluation could not attribute the change to the buses because street-lighting and licensing rules changed in the same period. Interviews with 180 passengers found that most had previously used taxis or lifts; only a minority had previously walked. The trial therefore offers weak support for claims that it removed large numbers of pedestrians from unsafe streets.

Critics noted that the subsidy per passenger remained above that of daytime buses. The authority replied that direct comparison ignored the social purpose of a service aimed at workers with few alternatives. Its final recommendation was neither permanent adoption nor cancellation. It proposed keeping the hospital route, redesigning the weakest route, and collecting weekday data before deciding whether a broader night network was justified.""",
        [
            _mcq(
                "Which conclusion is best supported by the passage?",
                [
                    "The entertainment-district route produced most of the trial's passenger growth.",
                    "Publicity by major employers was followed by increased use of the service.",
                    "Most night-bus passengers had previously walked home.",
                    "The trial met the daytime network's average occupancy.",
                ],
                "B",
                "B is correct because use rose after hospitals and warehouses promoted the timetables. A reverses the route comparison; C contradicts the interview finding; D confuses the minimum trial target with the higher daytime average.",
                "Medium",
            ),
            _mcq(
                "Why does the passage treat the reduction in taxi-rank disorder cautiously?",
                [
                    "The police stopped recording incidents on trial nights.",
                    "The reduction occurred only on the hospital route.",
                    "Other policy changes occurred during the same period.",
                    "Passenger interviews showed that disorder had increased elsewhere.",
                ],
                "C",
                "C is correct because lighting and licensing changed concurrently, preventing a causal attribution. A is invented; B confuses a bus route with the location of police data; D is unsupported because the interviews concerned prior travel, not disorder.",
                "Medium",
            ),
            _mcq(
                "The authority's response to the subsidy criticism rests mainly on which distinction?",
                [
                    "A socially targeted service may be judged by more than cost per passenger.",
                    "Night buses are cheaper to operate than daytime buses.",
                    "Venue levies covered the entire cost of all three routes.",
                    "Passengers on the hospital route paid higher fares.",
                ],
                "A",
                "A is correct: the authority argued that the service's social purpose made a simple cost comparison incomplete. B and D contradict or exceed the passage; C changes partial funding into full funding.",
                "Hard",
            ),
            _mcq(
                "Which best describes the authority's final position?",
                [
                    "The whole network should become permanent without alteration.",
                    "The trial should end because no route met its target.",
                    "Weekday services should replace all weekend services immediately.",
                    "Evidence supported selective continuation and further testing, not an all-or-nothing decision.",
                ],
                "D",
                "D is correct because the recommendation retained one route, redesigned another, and sought more data. A ignores redesign; B contradicts the occupancy result; C turns a proposal to gather weekday data into immediate replacement.",
                "Hard",
            ),
        ],
    ),
    (
        "VR",
        "Reading for the Main Idea",
        "Seeds Against an Uncertain Future",
        """Seed banks are often described as vaults built to rescue crops after catastrophe. That image is not entirely wrong, but it obscures their more frequent role. The Northvale collection distributes thousands of small seed samples each year to plant breeders and researchers. Most requests concern ordinary problems—resistance to a local fungus, tolerance of a shorter growing season, or the search for a flavour lost from commercial varieties—rather than recovery after a global disaster.

Preserving seeds is not simply a matter of keeping them cold. Some remain viable for decades when dried and frozen; others deteriorate quickly or cannot survive conventional storage at all. Northvale periodically germinates samples, grows the plants under controlled conditions, and harvests fresh seed. Each regeneration risks changing the collection: if only the fastest-germinating plants reproduce, rare traits may gradually disappear. Staff therefore grow enough plants to capture variation and isolate varieties that could cross-pollinate.

Digital catalogues create a different problem. A sample described only as “red bean, upland field” may have little value to a breeder who needs to know rainfall, soil, harvest date, and local use. Older accessions often lack such detail. Northvale works with regional museums and farming communities to reconstruct missing histories, but curators resist filling gaps with confident guesses. An incomplete record is frustrating; an invented one can misdirect years of research.

The collection cannot represent every crop population. Its managers prioritise material that is genetically distinctive, poorly represented elsewhere, or threatened in the place where it is grown. This creates disagreements. A seed bank may value a rare variety that produces little food, while a farming community may prefer support for a productive local crop. Northvale increasingly treats collection decisions as negotiations, recognising that conservation is not only about biological diversity but also about who defines what is worth saving.""",
        [
            _mcq(
                "What is the main purpose of the passage?",
                [
                    "To argue that seed banks should store only highly productive crops",
                    "To show why frozen storage has made field research unnecessary",
                    "To explain that maintaining a useful seed collection involves scientific and social choices",
                    "To prove that seed banks are mainly intended for recovery after global disasters",
                ],
                "C",
                "C is correct because the passage combines viability, regeneration, records, prioritisation, and community negotiation. A contradicts the final paragraph; B ignores regeneration and field work; D is the simplified image the opening qualifies.",
                "Medium",
            ),
            _mcq(
                "Why can regeneration alter a seed collection?",
                [
                    "Frozen seeds always mutate when first returned to soil.",
                    "Cross-pollination is required to preserve every variety.",
                    "Researchers select only plants with the best flavour.",
                    "Growing a narrow subset can reduce traits present in the stored population.",
                ],
                "D",
                "D is correct: reproducing only fast-germinating plants can remove rare variation. A and C are not stated; B reverses the need to isolate varieties that could cross-pollinate.",
                "Medium",
            ),
            _mcq(
                "The discussion of incomplete catalogues supports which inference?",
                [
                    "A short label is sufficient whenever the seed remains viable.",
                    "Accurate context can affect whether a sample is useful for a research question.",
                    "Museums hold more genetically diverse seeds than seed banks.",
                    "Curators routinely invent missing collection histories.",
                ],
                "B",
                "B is correct because environmental and historical context helps breeders judge relevance. A ignores the stated limitation; C is not compared; D contradicts the curators' caution.",
                "Hard",
            ),
            _mcq(
                "Which tension is highlighted in the final paragraph?",
                [
                    "Cold storage versus digital cataloguing",
                    "Global disasters versus local fungal disease",
                    "Genetic distinctiveness versus the immediate priorities of growers",
                    "Museums versus researchers over ownership of freezers",
                ],
                "C",
                "C is correct because managers may prioritise rarity while communities prioritise productive crops. A and B pair ideas without the stated conflict; D is invented.",
                "Hard",
            ),
        ],
    ),
    (
        "VR",
        "True / False / Can't Tell",
        "Mapping Heat Street by Street",
        """Citywide temperature records can conceal sharp local differences. In Calder, the official weather station stands in an open park, yet many residents live among dark roofs, narrow streets, and little vegetation. A university team therefore attached calibrated sensors to rubbish-collection vehicles, which followed nearly every residential street over six summer weeks. Each sensor recorded air temperature every five seconds.

The moving measurements produced detailed maps, but not a simple ranking of neighbourhoods. Collection rounds occurred at different times, and temperature changes rapidly after sunrise. Researchers adjusted readings using a fixed reference station and repeated several routes at contrasting times. Even after adjustment, they warned that a street measured on four mornings was less certain than one measured on twenty. The published map displayed uncertainty alongside estimated temperature rather than hiding it.

The hottest daytime streets were not always the warmest at night. Broad commercial roads with little shade heated strongly in sunshine but lost heat relatively quickly after shops closed. Dense residential blocks stored heat in walls and released it slowly, producing smaller daytime peaks but higher overnight temperatures. Tree cover was associated with cooler daytime readings, although the study did not establish that planting a tree in any location would produce the same reduction; building height, wind, and irrigation also varied.

Calder used the maps to place temporary drinking-water points and to prioritise inspections of rented flats during heat alerts. It did not redraw long-term planning zones immediately. Officials argued that six weeks of one summer could identify vulnerable locations for emergency action but was too narrow a basis for permanent building rules. The team has since installed stationary sensors in twelve contrasting streets to test whether the mobile survey's patterns recur across seasons and unusually cool as well as hot summers.""",
        [
            _vr_tfc(
                "Calder's official weather station is located in an open park.",
                "A",
                "The opening paragraph states this directly and contrasts it with where many residents live.",
                "Easy",
            ),
            _vr_tfc(
                "Some streets were measured on more mornings than other streets.",
                "A",
                "The passage contrasts a street measured on four mornings with one measured on twenty.",
            ),
            _vr_tfc(
                "Some commercial roads cooled more quickly after closing than dense residential blocks cooled overnight.",
                "A",
                "Commercial roads are described as losing heat relatively quickly, while dense residential blocks released stored heat slowly.",
            ),
            _vr_tfc(
                "The twelve stationary sensors recorded lower temperatures than the mobile sensors.",
                "C",
                "The passage states the purpose of the new sensors but gives no results from them.",
                "Hard",
            ),
        ],
    ),
    (
        "VR",
        "Inference & Author Tone",
        "The Box That Changed the Harbour",
        """Before standard freight containers became common, a ship might carry thousands of separately handled crates, sacks, and barrels. Cargo was moved between warehouse, lorry, dock, and hold by teams of workers who knew how to balance awkward loads. Ports competed partly on the speed and skill of this labour. Theft and damage were persistent risks because goods were repeatedly opened, counted, and shifted.

Metal containers had existed in several forms, but early systems were incompatible. A box designed for one railway wagon might not fit another company's crane or a ship's securing points. The decisive change was therefore not merely the invention of a strong box. Shipping firms, railways, manufacturers, and regulators eventually agreed on dimensions, corner fittings, and load ratings. Standardisation allowed the same sealed unit to travel across different transport networks.

The gains were substantial but uneven. Loading times fell and larger ships became economical, while many traditional dock jobs disappeared. Established inner-city ports often lacked space for container yards and road connections. New terminals developed on cheaper land farther from old waterfronts, drawing investment away from districts built around manual cargo handling. Some cities later converted abandoned docks into housing and offices, but redevelopment rarely employed the same people or used the same skills.

It is tempting to describe the container as an autonomous technology that swept aside resistance. In practice, adoption depended on public spending on roads and dredging, labour agreements, insurance rules, and the willingness of rivals to share standards. Nor did every cargo become containerised: bulk grain, oil, and unusually large machinery continued to use specialised systems. The container's importance lies less in universal replacement than in coordinating previously fragmented journeys for a large share of manufactured goods.""",
        [
            _mcq(
                "According to the passage, why did early metal-container systems fail to transform freight widely?",
                [
                    "The boxes were too fragile to be lifted by cranes.",
                    "Most manufactured goods legally had to remain in sacks.",
                    "Ports refused to employ workers who understood balanced loads.",
                    "Different transport systems lacked shared technical standards.",
                ],
                "D",
                "D is correct because incompatible dimensions and fittings prevented interchange. A, B, and C are not stated and do not address the interoperability problem.",
                "Medium",
            ),
            _mcq(
                "Which statement best captures the passage's view of containerisation's economic effects?",
                [
                    "Efficiency gains were accompanied by geographically and occupationally uneven costs.",
                    "Every port benefited once manual handling ended.",
                    "Waterfront redevelopment restored the same employment that had been lost.",
                    "Containerisation affected shipping firms but not cities or workers.",
                ],
                "A",
                "A is correct: faster loading and larger ships coincided with lost jobs and displaced investment. B and D ignore those costs; C contradicts the change in people and skills employed.",
                "Hard",
            ),
            _mcq(
                "The final paragraph primarily challenges which interpretation?",
                [
                    "Some freight still requires specialised handling.",
                    "The container succeeded through technology alone and replaced every cargo system.",
                    "Public infrastructure can influence private transport systems.",
                    "Standardisation can coordinate separate transport networks.",
                ],
                "B",
                "B is correct because the author rejects autonomous, universal technological replacement. A, C, and D are positions the paragraph supports rather than challenges.",
                "Medium",
            ),
            _mcq(
                "Which factor is presented as necessary for the same sealed unit to move across networks?",
                [
                    "Redeveloping old docks as offices",
                    "Keeping all containers within one shipping company",
                    "Agreement on dimensions, fittings, and load ratings",
                    "Replacing bulk carriers with larger container ships",
                ],
                "C",
                "C is correct because shared specifications created interchangeability. A concerns later land use; B contradicts cross-network movement; D is neither stated nor suitable for all cargo.",
                "Easy",
            ),
        ],
    ),
    (
        "VR",
        "Reading for the Main Idea",
        "A Frequency for the Valley",
        """The first broadcasts from Valley Voice were improvised. A transmitter borrowed from a college covered only part of the valley, and presenters recorded interviews in a room above a repair shop. The station was created after severe floods disrupted telephone and internet services. During the emergency, residents relied on a distant commercial station whose traffic reports rarely mentioned the valley's smaller roads.

Once the floods receded, volunteers disagreed about the station's purpose. Some wanted an emergency service that would remain silent between alerts. Others argued that a station unused for months would lose both its audience and the skills needed when a crisis returned. Valley Voice adopted a weekly schedule of local news, farming reports, music, and programmes in two minority languages. Emergency exercises were woven into ordinary broadcasting rather than treated as a separate activity.

Maintaining participation proved harder than attracting initial enthusiasm. Retired volunteers could cover daytime slots, while commuters and parents were available mainly in the evening. Training every presenter to verify reports slowed production but reduced the number of unconfirmed messages read on air. The station also created a rule that businesses providing equipment could be acknowledged but not influence editorial decisions. This cost it one large sponsor, although smaller donations increased after the policy was publicised.

An evaluation after four years found that awareness of flood procedures was highest among regular listeners. It could not show that the station caused this difference: regular listeners were also more likely to attend community meetings. However, a surprise emergency exercise revealed a practical advantage. Valley Voice switched to verified updates within seven minutes, whereas neighbouring areas had to assemble temporary communication teams. The evaluators concluded that routine broadcasting had preserved a functioning network of people and equipment, even if its wider effect on preparedness remained uncertain.""",
        [
            _mcq(
                "Why did Valley Voice continue ordinary programmes between emergencies?",
                [
                    "To replace every commercial station serving the region",
                    "To keep an audience and operational skills active",
                    "To guarantee that listeners attended community meetings",
                    "To allow sponsors to select the news agenda",
                ],
                "B",
                "B is correct because volunteers feared an otherwise dormant station would lose listeners and capability. A overstates its role; C confuses correlation with purpose; D contradicts the editorial rule.",
                "Medium",
            ),
            _mcq(
                "What trade-off accompanied the station's verification training?",
                [
                    "Faster production but more unconfirmed reports",
                    "Less local news but greater sponsor control",
                    "Slower production but fewer unconfirmed reports",
                    "Fewer presenters but wider transmitter coverage",
                ],
                "C",
                "C is correct and preserves both sides of the stated trade-off. A reverses it; B and D combine effects not linked in the passage.",
                "Easy",
            ),
            _mcq(
                "Why could the four-year evaluation not attribute greater preparedness awareness to the station?",
                [
                    "Regular listeners differed in another relevant behaviour.",
                    "The station had never broadcast flood information.",
                    "Neighbouring areas used the same presenters.",
                    "No regular listener knew the flood procedures.",
                ],
                "A",
                "A is correct because regular listeners were also more likely to attend meetings, creating an alternative explanation. B and D contradict the passage; C is not stated.",
                "Hard",
            ),
            _mcq(
                "Which conclusion best reflects the evaluators' final judgement?",
                [
                    "Routine broadcasting definitely caused higher preparedness throughout the valley.",
                    "The station's entertainment output mattered more than emergency communication.",
                    "Losing a large sponsor made the station unable to respond quickly.",
                    "Routine operation maintained response capacity, though its broader causal impact was unresolved.",
                ],
                "D",
                "D is correct because the exercise demonstrated operational readiness while the awareness evidence remained non-causal. A overclaims; B is not compared; C is contradicted by the seven-minute response.",
                "Hard",
            ),
        ],
    ),
    (
        "VR",
        "True / False / Can't Tell",
        "Giving the River Room",
        """For decades, the River Lorn was confined between high embankments as it crossed farmland. The channel moved water quickly downstream but disconnected the river from its floodplain. After repeated floods in the town below, engineers proposed lowering selected embankments and excavating shallow channels across two fields. During high flows, water could spread temporarily over land purchased for the project.

Some residents described the scheme as abandoning flood defence. Its designers argued that it redistributed protection rather than removing it: water stored upstream would reduce the volume arriving at the town during the same hours. Computer models predicted a modest reduction in peak level for common floods and little difference during the most extreme event tested. The team emphasised that the project would supplement, not replace, walls protecting the town centre.

The first controlled inundation occurred after heavy autumn rain. Gauges showed a lower peak than the modelled peak for an otherwise similar earlier storm, but rainfall location and soil moisture differed between the two events. Engineers therefore did not treat the comparison as a precise measurement of the scheme's effect. They will combine data from multiple floods with updated modelling.

Ecologists expected the new channels to create wet grassland. Within two years, wading birds fed in the shallow pools and several moisture-tolerant plants appeared. At the same time, an invasive plant colonised disturbed soil near one excavation. Removing it required repeated cutting, an expense omitted from the original maintenance estimate. Farmers outside the purchased area also asked whether higher groundwater might affect drainage, but monitoring has not yet run long enough to answer them. The project has produced early ecological and hydraulic signs of benefit, alongside costs and uncertainties that its supporters had initially understated.""",
        [
            _vr_tfc(
                "The scheme was designed to supplement the town-centre flood walls rather than replace them.",
                "A",
                "The designers make this relationship explicit in the second paragraph.",
                "Easy",
            ),
            _vr_tfc(
                "The models predicted the same reduction in water level for every size of flood.",
                "B",
                "They predicted a modest effect for common floods and little difference in the most extreme event tested.",
            ),
            _vr_tfc(
                "The first inundation proved exactly how much the scheme reduces a flood peak.",
                "B",
                "Rainfall distribution and prior soil moisture differed, so engineers rejected the comparison as a precise causal estimate.",
                "Hard",
            ),
            _vr_tfc(
                "Higher groundwater has reduced crop yields on farms outside the purchased area.",
                "C",
                "Farmers raised a concern about drainage, but monitoring had not established an effect on drainage or yields.",
                "Hard",
            ),
        ],
    ),
    (
        "VR",
        "Inference & Author Tone",
        "Voices in the Archive",
        """When linguists began recording the Aven language in the 1970s, they concentrated on word lists and formal narratives told by older men. The resulting archive is valuable, but it captures only a narrow register. It contains few conversations, children's games, work songs, or examples of speakers interrupting and correcting one another. Later researchers sometimes treated the archive as a complete picture of traditional Aven, mistaking what had been selected for what had existed.

A new community-led project is expanding the collection. Young speakers record family conversations with participants' consent, while craft workers describe processes as they perform them. Contributors decide whether recordings may be public, restricted to Aven families, or closed for a fixed period. These controls make the catalogue more complicated, yet organisers argue that an archive built by ignoring speakers' wishes would undermine the very community whose language it claims to preserve.

The project has also exposed disagreement about “correct” Aven. School materials developed from the old recordings favour one village's pronunciation. Speakers elsewhere use different endings and sometimes borrow words from the national language. Some elders regard these forms as decline; younger contributors see them as evidence that Aven remains useful in contemporary life. The archive records variants rather than selecting a single authorised form.

Recording more speech will not by itself reverse the fall in daily use. Employment and education draw young adults away from the region, and most public services operate in the national language. The project therefore funds conversation groups and works with local clinics to offer bilingual appointment information. Its organisers describe the archive as infrastructure: it can support teaching and public use, but only if people and institutions choose to use it. Preservation, in this account, is not freezing a language at an imagined pure moment; it is widening the situations in which speakers can carry it forward.""",
        [
            _mcq(
                "What limitation of the older archive does the author emphasise?",
                [
                    "Its recordings were made without any equipment.",
                    "Its selective contents were sometimes mistaken for a complete record.",
                    "It contains too many examples of informal conversation.",
                    "It focuses mainly on the speech of young children.",
                ],
                "B",
                "B is correct because later researchers mistook a narrow selection for the whole language. A is false; C and D reverse the omissions described.",
                "Medium",
            ),
            _mcq(
                "Why does the new project accept a more complicated catalogue?",
                [
                    "Access controls respect contributors while allowing different levels of use.",
                    "Restricted recordings are automatically more linguistically accurate.",
                    "A complicated catalogue prevents pronunciation from changing.",
                    "Public recordings are prohibited by national law.",
                ],
                "A",
                "A is correct because contributor-controlled access is presented as ethically necessary. B and C claim benefits not stated; D invents a legal prohibition.",
                "Hard",
            ),
            _mcq(
                "The treatment of regional variants suggests that the organisers view language as:",
                [
                    "authentic only when it excludes borrowed words.",
                    "best preserved by enforcing the pronunciation in school materials.",
                    "changing and contested rather than fixed in one authorised form.",
                    "incapable of being used in modern institutions.",
                ],
                "C",
                "C is correct because variants and borrowings are recorded rather than rejected. A and B take the elders' restrictive view; D is contradicted by work with clinics.",
                "Medium",
            ),
            _mcq(
                "Which statement best expresses the passage's final argument?",
                [
                    "Documentation is sufficient to restore daily language use.",
                    "A language survives only if young adults remain in one region.",
                    "Public services should replace archives with conversation groups.",
                    "Archives can enable revival, but continuing use depends on social choices beyond recording.",
                ],
                "D",
                "D is correct because the archive is described as infrastructure rather than a self-executing solution. A overstates recording; B turns one pressure into a sole condition; C falsely presents complementary measures as substitutes.",
                "Hard",
            ),
        ],
    ),
    (
        "VR",
        "Reading for the Main Idea",
        "The Quiet Infrastructure Under the Sea",
        """Most international data travels not by satellite but through fibre-optic cables laid across the seabed. Each cable carries pulses of light between landing stations, where traffic joins terrestrial networks. The route is invisible to ordinary users, which encourages the mistaken idea that digital communication is placeless. In fact, a message between nearby countries may depend on a small number of coastal sites, repair ships, and regulatory agreements.

Cable breaks are not unusual. Fishing gear, anchors, and undersea landslides cause most faults; deliberate interference receives more attention than its frequency warrants. Network operators usually redirect traffic while a repair ship locates the damaged section and raises it from the seabed. Rerouting can prevent a complete outage, but it may increase delay or overload remaining connections. Resilience therefore depends on spare capacity and genuinely diverse routes, not merely on counting how many cables appear on a map.

That distinction matters because apparently separate cables may share a landing station, power supply, or narrow marine corridor. A storm that closes one station can disable several routes at once. Some governments subsidise additional landings in different regions, even when the immediate commercial case is weak. Critics call this duplication; supporters compare it to maintaining emergency roads that are rarely full but become valuable when the main route fails.

Environmental concerns complicate expansion. Installation disturbs a narrow strip of seabed, while designated cable corridors can later discourage trawling and anchoring. Studies have found limited long-term effects in some habitats, but evidence is thinner in deep or biologically sensitive areas. Regulators must weigh the benefit of route diversity against uncertainty about local ecology. The central policy question is not whether cables have impacts or whether digital links matter—both are clear—but how much redundancy is worth building, where it should go, and who should pay for capacity that may sit unused until a failure.""",
        [
            _mcq(
                "Which misconception does the opening paragraph challenge?",
                [
                    "Digital communication does not depend on physical locations and infrastructure.",
                    "Fibre-optic cables can transmit pulses of light.",
                    "Landing stations connect marine and land networks.",
                    "Countries exchange data internationally.",
                ],
                "A",
                "A is correct because the passage contrasts an impression of placelessness with dependence on cables and coastal sites. B, C, and D are facts the paragraph accepts.",
                "Easy",
            ),
            _mcq(
                "Why can a network with several cables still lack resilience?",
                [
                    "Every cable is damaged mainly by deliberate interference.",
                    "Different cables may share a single vulnerable facility or corridor.",
                    "Repair ships cannot lift damaged cable from the seabed.",
                    "Rerouted traffic always causes a total outage.",
                ],
                "B",
                "B is correct because shared landings, power, or corridors create common failure points. A contradicts the frequency comparison; C is false; D changes possible delay or overload into an inevitable outage.",
                "Medium",
            ),
            _mcq(
                "The comparison with emergency roads is used to justify:",
                [
                    "prohibiting commercial operators from using spare capacity.",
                    "placing every cable in the same protected corridor.",
                    "building capacity whose value becomes apparent during disruption.",
                    "replacing damaged cables with satellite links.",
                ],
                "C",
                "C is correct because rarely full alternative routes provide resilience when the main route fails. A, B, and D are not supported and B would reduce diversity.",
                "Medium",
            ),
            _mcq(
                "Which best describes the final paragraph's position?",
                [
                    "Cable installation has no environmental effects in any habitat.",
                    "Ecological uncertainty makes route diversity unnecessary.",
                    "Commercial demand alone determines where resilient routes should be built.",
                    "Policy must balance resilience benefits, local uncertainty, and the cost of spare capacity.",
                ],
                "D",
                "D is correct because the conclusion frames a trade-off among redundancy, ecology, location, and payment. A overgeneralises limited findings; B and C ignore the stated policy balance.",
                "Hard",
            ),
        ],
    ),
    (
        "VR",
        "True / False / Can't Tell",
        "A Digital Return",
        """The Harland Museum holds carved panels removed from the island of Naro during a colonial military expedition. Naro's cultural council has requested their physical return. While negotiations continue, the museum has created high-resolution three-dimensional scans and supplied copies to a Naro heritage centre. Museum trustees describe this as a “digital return” that improves access without exposing the fragile originals to transport.

The council welcomes the scans for education but rejects the suggestion that they settle the ownership dispute. Digital models reproduce visible surfaces, not the panels' material, age, or ceremonial status. Some island artists use the models to study damaged motifs, while community leaders restrict particular images that were never intended for unrestricted viewing. The heritage centre therefore keeps one version on a controlled local server rather than placing every file online.

Scanning has also changed research in Harland. Curators discovered shallow marks that were difficult to see under gallery lighting, prompting a revised interpretation of how two panels were arranged. A later inspection of the originals showed pigment traces absent from the first digital models. The museum rescanned those areas and now treats each model as a record made with particular equipment at a particular time, not as a perfect substitute.

Negotiations over the objects have not concluded. The museum has offered a renewable long-term loan; the council argues that a loan would wrongly describe Naro as a borrower of its own heritage. Both sides have agreed that the digital files will remain in Naro regardless of the physical outcome. The scans have created useful access and new knowledge, but they have also made the distinction between information about an object and authority over it harder to ignore. Digital availability can widen participation while leaving the central question of possession untouched.""",
        [
            _vr_tfc(
                "The Naro cultural council regards the scans as a complete resolution of the ownership dispute.",
                "B",
                "The council values the scans for education but explicitly rejects their use as a settlement of ownership.",
                "Easy",
            ),
            _vr_tfc(
                "Every digital file supplied to Naro is freely available on the internet.",
                "B",
                "Some culturally restricted material is kept on a controlled local server rather than placed online.",
            ),
            _vr_tfc(
                "The first scans captured pigment traces later found on the originals.",
                "B",
                "The traces were absent from the first models and prompted rescanning.",
            ),
            _vr_tfc(
                "The museum will physically return the panels before the end of the year.",
                "C",
                "Negotiations remain unresolved and the passage gives no date or agreed physical outcome.",
                "Hard",
            ),
        ],
    ),
    (
        "VR",
        "Inference & Author Tone",
        "When Amateurs Watch the Sky",
        """Professional observatories collect more images than their staff can inspect manually. Citizen astronomy projects divide some of this material into small online tasks, asking volunteers to classify shapes, mark changes, or compare images taken at different times. The work is often described as crowdsourcing spare human attention, but successful projects do more than distribute pictures. They design tasks in which independent judgements can be combined and uncertainty can be measured.

In the StarTrace project, each image is seen by at least twelve volunteers. Straightforward cases produce rapid agreement. Images with divided votes are reviewed by experienced participants and, if necessary, by researchers. This process does not assume that a majority is always correct. Artificial images with known features are mixed into the stream, allowing the team to estimate how different volunteers perform and to give more weight to consistently reliable classifications.

Automation has not removed the volunteers. A machine-learning system now handles many clear cases, leaving people a higher proportion of faint, overlapping, or unusual objects. As a result, the number of images shown to volunteers fell while the average time per image rose. Comparing productivity before and after automation using only image counts would therefore be misleading. Researchers instead examine how many scientifically useful candidates are found and how much expert review each requires.

Occasionally, a volunteer notices something outside the requested categories. Early versions of the interface made such observations difficult to report because the project sought uniform answers. StarTrace added a free-text flag, accepting that most flags would not lead to discoveries. The change introduced extra review work but preserved a route for the unexpected. The project's history suggests that citizen science is most valuable neither as cheap labour nor as a celebration of unaided intuition. Its strength comes from systems that combine repeated human judgement, calibration, automation, and opportunities to question the categories themselves.""",
        [
            _mcq(
                "Why are artificial images included in the classification stream?",
                [
                    "To train volunteers to use professional telescopes",
                    "To prevent researchers from seeing disputed cases",
                    "To estimate classifier reliability using cases with known features",
                    "To ensure every image receives a unanimous vote",
                ],
                "C",
                "C is correct because known cases calibrate volunteer performance and weighting. A and B are not stated; D contradicts the existence of divided votes.",
                "Medium",
            ),
            _mcq(
                "Why would raw image counts give a misleading comparison after automation?",
                [
                    "Volunteers stopped participating when the machine was introduced.",
                    "The remaining human tasks were fewer but generally more difficult.",
                    "Researchers no longer recorded scientifically useful candidates.",
                    "Every automated classification required expert correction.",
                ],
                "B",
                "B is correct because automation removed clear cases and increased average time per human-reviewed image. A, C, and D are unsupported absolutes.",
                "Medium",
            ),
            _mcq(
                "What trade-off followed the addition of a free-text flag?",
                [
                    "It enabled unexpected observations but increased review work.",
                    "It reduced review work but prevented unusual discoveries.",
                    "It produced uniform answers but removed calibration images.",
                    "It replaced repeated judgements with unaided intuition.",
                ],
                "A",
                "A is correct because the new reporting route preserved unexpected observations at the cost of reviewing many unproductive flags. B reverses both effects; C and D are unrelated.",
                "Hard",
            ),
            _mcq(
                "Which best summarises the author's view of citizen astronomy?",
                [
                    "Volunteer majorities should replace professional review.",
                    "Automation makes human classification scientifically obsolete.",
                    "Its principal benefit is reducing researchers' labour costs.",
                    "Its value depends on a designed system combining human and automated strengths.",
                ],
                "D",
                "D is correct because the conclusion emphasises repetition, calibration, automation, and challenge to categories. A ignores expert review and weighting; B contradicts continued human use; C is the narrow 'cheap labour' account the author rejects.",
                "Hard",
            ),
        ],
    ),
]


DM_STANDALONE_QUESTIONS = [
    (
        "DM", "Syllogisms & Logical Deduction",
        *_mcq(
            "Every amber file is archived. No archived file can be edited. Some reports can be edited. Which conclusion necessarily follows?",
            [
                "Some reports are not amber files.",
                "No report is archived.",
                "Some amber files can be edited.",
                "Every file that is not amber can be edited.",
            ],
            "A",
            "A is necessary: the editable reports cannot be archived, and every amber file is archived, so those reports are not amber. B overgeneralises from some reports; C contradicts the first two premises; D reverses a necessary exclusion into a sufficient condition.",
            "Medium",
        ),
    ),
    (
        "DM", "Syllogisms & Logical Deduction",
        *_mcq(
            "No untrained employee supervises a laboratory. Some assistants are untrained. Every fellowship holder is an assistant. Which conclusion necessarily follows?",
            [
                "No assistant supervises a laboratory.",
                "Some assistants do not supervise a laboratory.",
                "Every trained assistant holds a fellowship.",
                "Some fellowship holders are untrained.",
            ],
            "B",
            "B follows because the assistants known to be untrained cannot supervise. A wrongly extends this to every assistant; C reverses the final premise; D assumes the untrained assistants are fellowship holders.",
            "Medium",
        ),
    ),
    (
        "DM", "Syllogisms & Logical Deduction",
        *_mcq(
            "No metal token glows. Every green token glows. At least one square token is green. Which conclusion necessarily follows?",
            [
                "Every square token glows.",
                "No square token is metal.",
                "At least one square token is not metal.",
                "Every non-metal token is green.",
            ],
            "C",
            "C follows through the green square: it glows, and nothing metal glows, so it is not metal. A says all squares rather than at least one; B makes the same overextension; D reverses the relationship between green and non-metal tokens.",
            "Medium",
        ),
    ),
    (
        "DM", "Syllogisms & Logical Deduction",
        *_mcq(
            "A parcel is sent by courier X or courier Y, but not both. If it is sent by Y, it arrives after Tuesday. The parcel did not arrive after Tuesday. Which statement must be true?",
            [
                "It was sent by courier Y.",
                "It was sent by courier X.",
                "Courier X always delivers before Tuesday.",
                "It arrived on Tuesday.",
            ],
            "B",
            "B is forced: not arriving after Tuesday rules out Y, and exactly one courier was used. A conflicts with the conditional; C generalises from one parcel to all X deliveries; D is not fixed because the parcel could have arrived earlier.",
            "Easy",
        ),
    ),
    (
        "DM", "Syllogisms & Logical Deduction",
        *_mcq(
            "Every grant that is renewed has either a progress review or an audit. No grant with an audit is renewed late. Grant K was renewed late and had no progress review. Which conclusion follows?",
            [
                "Grant K had an audit.",
                "Grant K was not renewed.",
                "Every late grant lacks an audit.",
                "The stated conditions cannot all be true of Grant K.",
            ],
            "D",
            "D is correct. Renewal plus no progress review forces an audit, but an audited grant cannot be renewed late, contradicting the remaining fact. A follows from only part of the premises but cannot coexist with all of them; B contradicts the stated renewal; C generalises beyond renewed grants.",
            "Hard",
        ),
    ),
    (
        "DM", "Logic Puzzles & Arrangements",
        *_mcq(
            "Five talks—J, K, L, M and N—are scheduled one per slot from 1 to 5. J is earlier than L. K is immediately after M. N is not in slot 1 or 5. L is not adjacent to K. Which schedule could be valid?",
            [
                "J, N, M, K, L",
                "M, K, L, N, J",
                "N, J, M, K, L",
                "J, L, N, M, K",
            ],
            "D",
            "D satisfies J before L, the M–K block, N in an interior slot, and non-adjacency of L and K. A places L adjacent to K; B puts J after L; C places N in slot 1 and also L adjacent to K.",
            "Medium",
        ),
    ),
    (
        "DM", "Logic Puzzles & Arrangements",
        *_mcq(
            "Four deliveries—P, Q, R and S—use different vans: blue, green, red and white. P is not blue or white. Q uses green or white. R does not use red. S uses blue. Which statement must be true?",
            [
                "P uses green.",
                "Q uses white.",
                "R uses red.",
                "P uses red.",
            ],
            "D",
            "D is necessary: S takes blue; P can use only green or red, but if P used green then Q would have to use white and R would be forced to red, which R cannot use. Therefore P is red. A is the impossible branch; B can be false when Q is green; C contradicts the clue.",
            "Hard",
        ),
    ),
    (
        "DM", "Logic Puzzles & Arrangements",
        *_mcq(
            "A clinic assigns Ana, Bilal, Chen and Devi to four consecutive shifts. Bilal works before Ana, Ana works before Chen, and Devi works immediately before Ana. Which person must work the final shift?",
            ["Ana", "Bilal", "Chen", "Devi"],
            "C",
            "C is necessary. The consecutive Devi–Ana block must come after Bilal, leaving the only order Bilal–Devi–Ana–Chen. A must precede Chen; B must precede Ana; D is immediately before Ana.",
            "Hard",
        ),
    ),
    (
        "DM", "Logic Puzzles & Arrangements",
        *_mcq(
            "Six books—F, G, H, J, K and L—are placed in a row. F is somewhere left of H. J is immediately left of K. G is at one end. L is not next to H. Which arrangement is possible?",
            [
                "G, J, K, H, L, F",
                "F, H, J, K, L, G",
                "G, H, F, J, K, L",
                "L, F, H, K, J, G",
            ],
            "B",
            "B satisfies F before H, keeps J immediately before K, puts G at an end, and separates L from H. A has F after H and L next to H; C has F after H; D reverses the J–K block.",
            "Medium",
        ),
    ),
    (
        "DM", "Logic Puzzles & Arrangements",
        *_mcq(
            "A panel selects exactly three of five proposals: A, B, C, D and E. If A is selected, B is selected. C and D cannot both be selected. At least one of D or E is selected. If E is selected, C is selected. Which selection is possible?",
            ["A, B, D", "A, C, E", "B, C, D", "B, D, E"],
            "A",
            "A is possible: selecting A includes B, C and D are not both present, and D satisfies the final condition. B omits the B required by A; C selects incompatible C and D; D selects E without the required C.",
            "Hard",
        ),
    ),
    (
        "DM", "Evaluating Arguments",
        *_mcq(
            "Should a town replace some central car-parking spaces with secure bicycle storage? Which is the strongest argument in favour?",
            [
                "Yes, because a travel survey found unmet demand for secure cycle parking and the affected car park usually has spare capacity nearby.",
                "Yes, because cycling is more enjoyable than driving for many people.",
                "Yes, because every modern town already provides bicycle storage.",
                "Yes, because bicycles are available in several colours.",
            ],
            "A",
            "A directly addresses demand and the principal cost of removing spaces with relevant local evidence. B relies on preference without showing need; C makes an unsupported universal claim; D is irrelevant to the decision.",
            "Medium",
        ),
    ),
    (
        "DM", "Evaluating Arguments",
        *_mcq(
            "Should a university library remain open two hours later during examinations? Which is the strongest argument against?",
            [
                "No, because some students prefer studying in the morning.",
                "No, because libraries used to close earlier in previous decades.",
                "No, because the staffing and security cost per additional user is high in data from a comparable trial, while alternative study rooms already have spare late capacity.",
                "No, because examinations are stressful.",
            ],
            "C",
            "C directly weighs evidenced cost against an available substitute. A does not address students who need late access; B appeals to tradition; D states a relevant context but not a reason the proposed opening is ineffective or disproportionate.",
            "Hard",
        ),
    ),
    (
        "DM", "Evaluating Arguments",
        *_mcq(
            "Should cafés be required to charge a small fee for disposable cups? Which is the strongest argument in favour?",
            [
                "Yes, because a fee gives customers a reason to choose reusable cups and trials measured a substantial fall in disposable-cup use.",
                "Yes, because reusable cups often have attractive designs.",
                "Yes, because no customer should ever buy a hot drink away from home.",
                "Yes, because some café owners dislike washing cups.",
            ],
            "A",
            "A links the policy mechanism to measured behaviour and directly addresses waste. B is aesthetic and immaterial; C is an extreme claim unrelated to the limited proposal; D could count against reuse and does not support the requirement.",
            "Medium",
        ),
    ),
    (
        "DM", "Evaluating Arguments",
        *_mcq(
            "Should a college move the first lesson from 08:00 to 09:00? Which is the strongest argument against?",
            [
                "No, because 08:00 is an even number.",
                "No, because changing timetables is always wrong.",
                "No, because one lecturer enjoys arriving early.",
                "No, because a later start would finish after the last affordable bus for many students unless transport arrangements also change.",
            ],
            "D",
            "D identifies a substantial access consequence that directly bears on the proposal. A is irrelevant; B is an unsupported absolute; C gives one preference without showing an important effect on students or provision.",
            "Medium",
        ),
    ),
    (
        "DM", "Evaluating Arguments",
        *_mcq(
            "Should a hospital provide translated appointment instructions for the five most-used languages among its patients? Which is the strongest argument in favour?",
            [
                "Yes, because translated instructions can reduce avoidable misunderstanding for a sizeable identified group, while interpreters remain available for individual discussion.",
                "Yes, because every patient speaks at least five languages.",
                "Yes, because printed pages look more professional when they contain several scripts.",
                "Yes, because clinicians should no longer explain appointments verbally.",
            ],
            "A",
            "A directly addresses communication risk, scale, and the limits of written translation. B is false and unnecessary; C is cosmetic; D proposes replacing rather than supporting communication and exceeds the question.",
            "Hard",
        ),
    ),
    (
        "DM", "Venn Diagrams & Sets",
        *_mcq(
            "Among 120 staff, 68 hold first-aid certification, 54 hold fire-safety certification and 49 hold manual-handling certification. Inclusive overlaps are 25 first-aid/fire, 22 first-aid/manual and 20 fire/manual; 8 hold all three. How many hold only first-aid certification?",
            ["21", "29", "37", "51"],
            "B",
            "B is correct: first-aid only = 68 − 25 − 22 + 8 = 29, adding the triple overlap back because it was subtracted twice. A omits adding back the triple; C subtracts only one pair overlap; D subtracts the triple rather than the pair overlaps.",
            "Medium",
        ),
    ),
    (
        "DM", "Venn Diagrams & Sets",
        *_mcq(
            "In a group of 96 students, 51 study French, 44 study German and 38 study Spanish. Twenty study both French and German, 18 both French and Spanish, 16 both German and Spanish, and 9 study all three. How many study none of the three languages?",
            ["6", "12", "10", "8"],
            "D",
            "D is correct: union = 51 + 44 + 38 − 20 − 18 − 16 + 9 = 88, so none = 96 − 88 = 8. A omits part of an overlap; B adds the triple overlap incorrectly; C subtracts the triple twice.",
            "Hard",
        ),
    ),
    (
        "DM", "Venn Diagrams & Sets",
        *_mcq(
            "A survey of 150 households found that 92 subscribe to a film service, 71 to a sports service and 63 to a documentary service. Twenty-eight subscribe to film and sports, 24 to film and documentary, 19 to sports and documentary, and 11 to all three. How many subscribe to exactly two of the services?",
            ["38", "49", "60", "71"],
            "A",
            "A is correct: exactly two = (28 − 11) + (24 − 11) + (19 − 11) = 38. B subtracts the triple only twice; C counts some triple subscribers more than once; D is the sports total, not the requested region.",
            "Hard",
        ),
    ),
    (
        "DM", "Venn Diagrams & Sets",
        *_mcq(
            "A warehouse has 180 parcels. Ninety-eight are fragile, 76 are express and 64 are insured. Forty are fragile and express, 35 are fragile and insured, 29 are express and insured, and 18 have all three labels. How many have exactly one of the three labels?",
            ["48", "60", "84", "72"],
            "C",
            "C is correct: fragile-only 41, express-only 25, insured-only 18, totalling 84. A forgets to add the triple overlap back within each only-region; B counts only two categories; D undercounts the insured-only region.",
            "Hard",
        ),
    ),
    (
        "DM", "Venn Diagrams & Sets",
        *_mcq(
            "Every member of a club plays chess, tennis, or both. Of 84 members, 47 play chess. There are 13 more tennis-only players than chess-only players, and 19 play both. How many play tennis?",
            ["50", "56", "60", "69"],
            "C",
            "C is correct: chess-only = 47 − 19 = 28; tennis-only = 28 + 13 = 41; tennis total = 41 + 19 = 60. A omits part of the tennis-only difference; B adds the overlap to chess-only incorrectly; D counts the 13-person difference twice.",
            "Medium",
        ),
    ),
    (
        "DM", "Probability & Statistics",
        *_mcq(
            "A box contains 5 amber, 4 blue and 3 white tiles. Two tiles are drawn without replacement. What is the probability that both are the same colour?",
            ["19/66", "23/66", "1/3", "5/11"],
            "A",
            "A is correct: same-colour pairs = C(5,2)+C(4,2)+C(3,2)=19 from C(12,2)=66 total pairs. B double-counts a colour; C treats the three colours as equally likely outcomes; D ignores the second draw's changed denominator.",
            "Medium",
        ),
    ),
    (
        "DM", "Probability & Statistics",
        *_mcq(
            "A screening programme tests 1,000 people. Two hundred have the condition. The test is positive for 180 of those 200 and also for 80 people without the condition. If one positive result is selected at random, what is the probability that it came from a person with the condition?",
            ["18%", "69.2%", "80%", "90%"],
            "B",
            "B is correct: 180 of 260 positive results are true positives, so 180/260 = 69.2%. A divides true positives by the whole group; C uses specificity-like data; D is sensitivity among those with the condition, not the probability after a positive result.",
            "Hard",
        ),
    ),
    (
        "DM", "Probability & Statistics",
        *_mcq(
            "A college estimates meal satisfaction by surveying the first 120 students leaving its premium dining hall. Ninety per cent are satisfied. Which is the most important limitation when applying this result to all students?",
            [
                "The percentage can never be converted to a fraction.",
                "The sample includes more than one hundred people.",
                "Satisfied students are unable to complete surveys accurately.",
                "Students from one premium hall may not represent the whole student population.",
            ],
            "D",
            "D identifies selection bias from a non-representative location. A is mathematically false; B is not a limitation by itself; C makes an unsupported claim about one response group.",
            "Medium",
        ),
    ),
    (
        "DM", "Probability & Statistics",
        *_mcq(
            "A fair spinner lands on red with probability 0.4. If it lands on red, a player wins with probability 0.75; otherwise the player wins with probability 0.20. What is the overall probability of winning?",
            ["0.30", "0.38", "0.42", "0.47"],
            "C",
            "C is correct: 0.4×0.75 + 0.6×0.20 = 0.42. A counts only red-and-win; B multiplies the two win probabilities; D adds probabilities without weighting by the spinner outcomes.",
            "Medium",
        ),
    ),
    (
        "DM", "Interpreting Information",
        *_mcq(
            "A service handled requests as follows:\n\n| Month | Requests | Resolved within target | Reopened |\n|---|---:|---:|---:|\n| April | 480 | 384 | 24 |\n| May | 520 | 442 | 39 |\n| June | 450 | 369 | 18 |\n\nWhich month had the highest percentage resolved within target, and what was that percentage?",
            ["May, 85%", "April, 80%", "June, 82%", "May, 92%"],
            "A",
            "A is correct: April 80%, May 442/520 = 85%, June 82%. B and C identify real rates but not the highest; D divides using an incorrect denominator.",
            "Medium",
        ),
    ),
    (
        "DM", "Interpreting Information",
        *_mcq(
            "Four trains leave Westport for Eastbay. Train A leaves 08:10 and takes 74 minutes. B leaves 08:25 and takes 61 minutes. C leaves 08:40 and takes 55 minutes. D leaves 08:50 and takes 48 minutes. A passenger reaches Westport at 08:22 and needs 4 minutes to board. Which available train arrives first?",
            ["Train A", "Train D", "Train C", "Train B"],
            "D",
            "D is available after boarding and arrives at 09:26. A cannot be boarded; C arrives 09:35; B arrives 09:38. The shortest journey is not the earliest arrival.",
            "Medium",
        ),
    ),
    (
        "DM", "Interpreting Information",
        *_mcq(
            "A shop begins with 240 units. On Monday it sells 25% of the opening stock. On Tuesday it receives 45 units, then sells one third of the stock then available. On Wednesday 12 returned units are added. How many units are present after Wednesday's returns?",
            ["132", "150", "162", "177"],
            "C",
            "C is correct: 240−60=180; add 45 to get 225; sell 75 to leave 150; add 12 to get 162. A omits the returns and also misuses Tuesday's base; B stops before returns; D subtracts one third of Monday's remaining stock.",
            "Medium",
        ),
    ),
    (
        "DM", "Interpreting Information",
        *_mcq(
            "In a trial, 12 of 300 people receiving programme X experienced an event, compared with 18 of 300 receiving programme Y. Which statement is justified by these figures alone?",
            [
                "Programme X prevents every event that Y would cause.",
                "The event rate was 2 percentage points lower in the X group than in the Y group.",
                "X will always produce the lower rate in any population.",
                "The difference proves that X caused the reduction.",
            ],
            "B",
            "B is the direct calculation: 4% versus 6%, a 2-percentage-point difference. A invents individual causation; C generalises beyond the data; D claims causality without information about allocation, uncertainty, or confounding.",
            "Hard",
        ),
    ),
    (
        "DM", "Interpreting Information",
        *_mcq(
            "A survey reports that neighbourhoods with more public gardens also have higher average walking rates. Which additional finding would most strengthen the claim that the gardens themselves increase walking?",
            [
                "Residents of greener neighbourhoods also have higher incomes.",
                "Walking rates rose in comparable neighbourhoods after gardens opened but not in matched neighbourhoods without new gardens.",
                "People who enjoy gardening often buy walking shoes.",
                "The largest garden contains more plants than the smallest garden.",
            ],
            "B",
            "B adds a before-and-after comparison with a matched control, reducing alternative explanations. A introduces a confounder; C is indirect and selective; D describes garden size without linking opening to walking behaviour.",
            "Hard",
        ),
    ),
]


DM_YESNO_QUESTIONS = [
    (
        "DM", "Syllogisms & Logical Deduction",
        "Every coral marker is waterproof. No waterproof marker is made of paper. Some red markers are coral markers. For each conclusion, answer Yes only if it necessarily follows.",
        "At least one red marker is waterproof.",
        "No coral marker is made of paper.",
        "Every red marker is a coral marker.",
        "Some red markers are not made of paper.",
        "Every non-paper marker is waterproof.",
        "A,B,D",
        "A Yes: the red coral marker is waterproof. B Yes: coral implies waterproof and waterproof excludes paper. C No: only some red markers are coral. D Yes: the same red coral marker cannot be paper. E No: the premises do not say all non-paper markers are waterproof.",
        "Medium",
    ),
    (
        "DM", "Syllogisms & Logical Deduction",
        "All bronze passes permit entry to Hall 1. Some passes that permit Hall 1 also permit Hall 2. No temporary pass permits Hall 2. For each conclusion, answer Yes only if it necessarily follows.",
        "Some passes permit both Hall 1 and Hall 2.",
        "No bronze pass is temporary.",
        "Some passes that permit Hall 1 are not temporary.",
        "Every pass for Hall 2 is bronze.",
        "A temporary pass might permit Hall 1.",
        "A,C",
        "A Yes: the second premise states an overlap. B No: bronze passes could be temporary if they permit only Hall 1. C Yes: the Hall-2 overlap cannot be temporary. D No: Hall-2 passes need not be bronze. E No: a temporary Hall-1 pass is possible, but its existence is not guaranteed by the premises.",
        "Hard",
    ),
    (
        "DM", "Syllogisms & Logical Deduction",
        "Every oak in the reserve is tagged. Some tagged trees are diseased. No diseased tree is open to visitors. Some oaks are open to visitors. For each conclusion, answer Yes only if it necessarily follows.",
        "Some tagged trees are not diseased.",
        "No oak is diseased.",
        "Some trees open to visitors are tagged.",
        "Every untagged tree is open to visitors.",
        "Some diseased trees are not oaks.",
        "A,C",
        "A Yes: the open oaks are tagged and cannot be diseased. B No: other oaks could be diseased. C Yes: the stated open oaks are tagged. D No: nothing is said about all untagged trees. E No: diseased tagged trees could all be oaks or all be non-oaks.",
        "Hard",
    ),
    (
        "DM", "Syllogisms & Logical Deduction",
        "No silver ticket is refundable. Every weekend ticket is refundable. Some discounted tickets are silver. No complimentary ticket is discounted. For each conclusion, answer Yes only if it necessarily follows.",
        "No weekend ticket is silver.",
        "Some discounted tickets are not refundable.",
        "Every refundable ticket is a weekend ticket.",
        "Some silver tickets are not complimentary.",
        "No complimentary ticket is silver.",
        "A,B,D",
        "A Yes: weekend implies refundable, which silver excludes. B Yes: the discounted silver tickets are non-refundable. C No: the implication cannot be reversed. D Yes: discounted silver tickets cannot be complimentary. E No: complimentary and silver may overlap provided those tickets are not discounted.",
        "Medium",
    ),
    (
        "DM", "Syllogisms & Logical Deduction",
        "All evening workshops require booking. No free event requires booking. Some music events are evening workshops. Every outdoor event is free. For each conclusion, answer Yes only if it necessarily follows.",
        "Some music events require booking.",
        "No evening workshop is free.",
        "Some music events are not outdoor events.",
        "Every event that requires booking is an evening workshop.",
        "No outdoor event is an evening workshop.",
        "A,B,C,E",
        "A Yes: the stated music workshops require booking. B Yes: booked and free are mutually exclusive. C Yes: those booked music events cannot be free and therefore cannot be outdoor. D No: booking may be required for other reasons. E Yes: outdoor implies free, while evening implies booked and no free event is booked.",
        "Hard",
    ),
    (
        "DM", "Syllogisms & Logical Deduction",
        "Every ceramic sample is fragile. Some fragile samples are insured. No insured sample is stored on shelf Z. All blue samples are stored on shelf Z. For each conclusion, answer Yes only if it necessarily follows.",
        "No blue sample is insured.",
        "Some fragile samples are not stored on shelf Z.",
        "Every ceramic sample is insured.",
        "Some insured samples are fragile.",
        "No ceramic sample is blue.",
        "A,B,D",
        "A Yes: blue implies shelf Z and insured excludes shelf Z. B Yes: the insured fragile samples cannot be on Z. C No: fragile does not imply insured. D Yes: it restates the given overlap. E No: a ceramic sample may be blue if it is fragile but uninsured.",
        "Medium",
    ),
]


QR_PASSAGE_SETS = [
    (
        "QR", "Tables, Charts & Data", "Riverside Leisure Centre",
        """Riverside offers the following prices. A second Plus membership in the same household receives 15% off the monthly membership fee. The discount does not apply to admissions.

| Plan | Monthly fee | Swim admission | Exercise class | Guest admission |
|---|---:|---:|---:|---:|
| Standard | £28.00 | £3.60 | £5.20 | £6.50 |
| Plus | £42.00 | Included | £2.80 | £5.50 |
| No membership | £0 | £7.00 | £8.50 | £8.00 |""",
        [
            _mcq(
                "In one month, a Standard member attends 6 swims and 3 exercise classes. What is the total cost?",
                ["£65.20", "£61.60", "£72.40", "£77.60", "£86.20"], "A",
                "A is correct: £28 + 6×£3.60 + 3×£5.20 = £65.20. B omits one swim; C applies Plus class prices to a Standard plan; D uses 8 swims; E uses non-member admissions as well as the membership fee.", "Medium"),
            _mcq(
                "A member attends 8 swims and 4 classes in a month. How much cheaper is Plus than Standard?",
                ["£18.00", "£24.40", "£28.80", "£31.20", "£35.60"], "B",
                "B is correct: Standard costs £28 + £28.80 + £20.80 = £77.60; Plus costs £42 + £11.20 = £53.20; saving £24.40. A compares fees only; C is the Standard swim cost; D omits a Plus class; E treats all Plus classes as free.", "Hard"),
            _mcq(
                "Two people in one household each hold Plus membership for 3 months. They also buy 4 guest admissions in total. What do they pay altogether?",
                ["£233.10", "£246.00", "£255.10", "£264.00", "£274.10"], "C",
                "C is correct: monthly fees are £42 + £35.70 = £77.70; over 3 months this is £233.10, plus 4×£5.50 = £22, giving £255.10. A omits guests; B ignores the household discount but omits guests; D ignores the discount; E applies the discount to guest entries incorrectly.", "Medium"),
            _mcq(
                "A person expects 10 swims each month. What is the minimum number of classes at which Plus becomes cheaper than Standard?",
                ["7", "8", "9", "10", "11"], "D",
                "D is correct. Standard costs £64 + £5.20c and Plus costs £42 + £2.80c. Plus is cheaper when £22 < £2.40c, so c must be at least 10. A (7), B (8), and C (9) stop before the strict break-even threshold; E (11) is one class more than necessary.", "Hard"),
        ]),
    (
        "QR", "Tables, Charts & Data", "Parcel Delivery Quotes",
        """A courier charge is calculated from the table. A 5% fuel levy is applied to the complete subtotal, including any surcharge. Weights are charged exactly unless a question specifies whole kilograms.

| Courier | Base charge | Per kg | Per km | Optional surcharge |
|---|---:|---:|---:|---:|
| Northline | £6.00 | £0.80 | £0.15 | Weekend: 20% of pre-levy subtotal |
| Swift | £9.00 | £0.55 | £0.12 | Rural address: £4.00 |
| ParcelGo | £4.50 | £1.10 | £0.10 | Signature: £2.50 |""",
        [
            _mcq(
                "An 8 kg parcel travels 40 km on a weekday with no optional surcharge. Which courier is cheapest after the fuel levy, and what does it charge?",
                ["Northline, £18.40", "Swift, £18.20", "Northline, £19.32", "Swift, £19.11", "ParcelGo, £18.17"], "E",
                "E is correct: ParcelGo subtotal £17.30 becomes £18.165, rounded to £18.17. A and B omit the levy; C and D are the levied Northline and Swift prices, both higher.", "Medium"),
            _mcq(
                "What does Northline charge to send a 12 kg parcel 60 km at the weekend? Give the answer to the nearest penny.",
                ["£31.00", "£29.52", "£30.75", "£31.99", "£34.02"], "A",
                "A is correct: subtotal £6 + £9.60 + £9 = £24.60; weekend surcharge gives £29.52; the 5% levy gives £30.996, or £31.00. B stops before the levy; C applies 5% before the weekend percentage incorrectly; D rounds an intermediate value badly; E applies the weekend percentage twice.", "Hard"),
            _mcq(
                "A 5 kg parcel travels 25 km to a rural address. Compare Swift with ParcelGo when a signature is required. How much cheaper is ParcelGo after the levy?",
                ["£3.00", "£3.94", "£4.00", "£4.14", "£5.19"], "B",
                "B is correct: Swift is (£9+£2.75+£3+£4)×1.05 = £19.69; ParcelGo is (£4.50+£5.50+£2.50+£2.50)×1.05 = £15.75; difference £3.94. A compares incomplete subtotals; C uses the rural surcharge alone; D applies the levy to the difference twice; E omits ParcelGo's signature charge.", "Hard"),
            _mcq(
                "For a weekday Northline delivery over 50 km, what is the greatest whole-number weight that keeps the final charge at or below £25?",
                ["10 kg", "11 kg", "12 kg", "13 kg", "14 kg"], "C",
                "C is correct: (6 + 7.50 + 0.80w)×1.05 ≤ 25, giving w ≤ 12.886, so the greatest whole kg is 12. A and B are unnecessarily low; D and E exceed the cap.", "Hard"),
        ]),
    (
        "QR", "Percentages & Percentage Change", "Household Water Use",
        """Monthly water charges are £8 plus tiered usage: the first 15 m³ costs £1.20 per m³, the next 15 m³ costs £1.65 per m³, and usage above 30 m³ costs £2.10 per m³. A £5 conservation rebate is deducted when monthly use is 20 m³ or less.

| Household | April | May | June |
|---|---:|---:|---:|
| A | 18 m³ | 22 m³ | 31 m³ |
| B | 12 m³ | 17 m³ | 24 m³ |
| C | 26 m³ | 29 m³ | 35 m³ |
| D | 15 m³ | 20 m³ | 28 m³ |""",
        [
            _mcq(
                "What is Household C's water charge for June?",
                ["£53.25", "£55.75", "£59.15", "£61.25", "£66.25"], "D",
                "D is correct: £8 + 15×£1.20 + 15×£1.65 + 5×£2.10 = £61.25. A omits part of the second tier; B applies the top rate only to 3 m³; C omits the standing charge; E incorrectly removes a rebate from a different subtotal.", "Medium"),
            _mcq(
                "By what percentage did Household B's use increase from April to June?",
                ["50%", "70.6%", "82.4%", "92%", "100%"], "E",
                "E is correct: use doubled from 12 to 24 m³, so the increase is 12/12 = 100%. A divides by the final use; B compares April with May; C uses May as the denominator; D confuses percentage-point style subtraction with percentage change.", "Easy"),
            _mcq(
                "What is Household D's charge for May after the conservation rebate?",
                ["£29.25", "£31.50", "£34.25", "£37.25", "£42.25"], "A",
                "A is correct: £8 + 15×£1.20 + 5×£1.65 − £5 = £29.25. B applies one rate to all use; C omits the rebate; D charges the second tier at £2.10; E adds rather than subtracts the rebate.", "Medium"),
            _mcq(
                "Combined use by all four households rose from April to June. What was the percentage increase, to 1 decimal place?",
                ["39.8%", "66.2%", "47.0%", "60.1%", "71.4%"], "B",
                "B is correct: April total 71 m³, June total 118 m³; increase 47/71×100 = 66.2%. A uses June as denominator; C reports the absolute increase as a percentage; D omits Household D; E rounds after using the wrong base.", "Hard"),
        ]),
    (
        "QR", "Ratios & Proportion", "Travel-Money Exchange",
        """An exchange desk uses the following rates and charges. Calculations are rounded only at the final step.

| Currency | Customer receives | Charge |
|---|---:|---|
| euro (€) | €1.16 per £1 | 1.5% of sterling exchanged, deducted before conversion |
| Polish zloty (zł) | zł5.02 per £1 | £6 added to the sterling cost |
| Danish krone (kr) | kr13.40 per £1 | 2% of the converted krone amount deducted |

For unused euros, the desk pays £0.82 per €1 and then deducts a £4 return fee.""",
        [
            _mcq(
                "How many euros does a customer receive for exchanging £620?",
                ["€697.20", "€701.44", "€708.41", "€719.20", "€730.00"], "C",
                "C is correct: £620×0.985×1.16 = €708.412, or €708.41. A deducts 3%; B applies the fee after an incorrect conversion; D ignores the fee; E adds the fee.", "Medium"),
            _mcq(
                "A traveller needs zł2,900. How many pounds must be paid, including the charge? Give the answer to the nearest penny.",
                ["£565.71", "£571.53", "£577.69", "£583.69", "£589.71"], "D",
                "D is correct: £2,900/5.02 = £577.69 for the currency, plus £6 = £583.69. A multiplies rather than divides after rescaling; B subtracts the fee; C omits it; E adds the fee twice.", "Hard"),
            _mcq(
                "How many Danish kroner does a customer receive for £400 after the charge?",
                ["kr5,040.00", "kr5,145.60", "kr5,200.00", "kr5,252.00", "kr5,252.80"], "E",
                "E is correct: £400×13.40 = kr5,360; after 2% deduction, kr5,252.80 remains. A uses the euro fee; B deducts 4%; C rounds before applying the fee; D drops the final 0.80.", "Medium"),
            _mcq(
                "A traveller returns €250. How many pounds are paid after the return fee?",
                ["£201.00", "£205.00", "£209.00", "£211.50", "£213.00"], "A",
                "A is correct: €250×£0.82 = £205, then £4 is deducted to give £201. B omits the fee; C adds it; D uses €0.82 as if it were pounds per £1; E applies the original 1.5% fee instead.", "Easy"),
        ]),
    (
        "QR", "Tables, Charts & Data", "Print Workshop Capacity",
        """Four printers have different setup times, speeds, waste rates and paper costs. Waste rate is the proportion of printed sheets that is unusable. Whole sheets must be printed. Setup occurs once per job.

| Printer | Setup | Speed | Waste | Cost per printed sheet |
|---|---:|---:|---:|---:|
| A | 12 min | 38 sheets/min | 4% | £0.031 |
| B | 18 min | 52 sheets/min | 7% | £0.028 |
| C | 8 min | 44 sheets/min | 5% | £0.030 |
| D | 6 min | 40 sheets/min | 3% | £0.032 |""",
        [
            _mcq(
                "Using printer B, approximately how long does a job requiring 1,800 usable sheets take, including setup?",
                ["52.6 min", "55.2 min", "56.7 min", "57.4 min", "59.9 min"], "B",
                "B is correct: ceil(1800/0.93)=1,936 sheets; 1,936/52 + 18 = 55.23 minutes. A omits some waste; C rounds the usable requirement upward twice; D uses printer C's speed; E adds the waste percentage to time.", "Hard"),
            _mcq(
                "What is the paper cost for 2,200 usable sheets printed on C?",
                ["£66.00", "£67.80", "£69.48", "£69.60", "£72.95"], "C",
                "C is correct: ceil(2200/0.95)=2,316 printed sheets; ×£0.030 = £69.48. A ignores waste; B uses too few replacement sheets; D rounds printed sheets to the next ten; E uses printer D's cost.", "Medium"),
            _mcq(
                "Which printer completes 1,000 usable sheets fastest, including setup?",
                ["A", "B", "C", "D", "A and D tie"], "D",
                "D is correct: times are approximately A 39.4, B 38.7, C 31.9 and D 31.8 minutes. A and B have faster or comparable running speeds but longer setup/waste effects; C is close but slower; E is false.", "Hard"),
            _mcq(
                "What is the greatest number of usable whole sheets printer A can produce in 75 minutes, including setup?",
                ["2,184", "2,280", "2,294", "2,300", "2,298"], "E",
                "E is correct: 63 running minutes produce 2,394 sheets; 96% usable = 2,298.24, so 2,298 whole usable sheets. A applies waste twice; B rounds to hundreds; C subtracts 4% of the time; D rounds usable sheets up.", "Medium"),
        ]),
    (
        "QR", "Speed, Distance & Time", "Harbour Ferry Timetable",
        """The sea distance between Harbour and Leyton is 72 km. Passengers must be ready to board 15 minutes before departure. Advance tickets reduce the listed fare by 12%; bicycle charges are not discounted.

| Direction | Depart | Arrive | Fare |
|---|---:|---:|---:|
| Harbour → Leyton | 07:35 | 09:05 | £28 |
| Harbour → Leyton | 09:20 | 10:42 | £34 |
| Harbour → Leyton | 11:10 | 12:30 | £31 |
| Leyton → Harbour | 15:15 | 16:40 | £30 |
| Leyton → Harbour | 17:05 | 18:27 | £27 |
| Leyton → Harbour | 19:10 | 20:45 | £24 |

A bicycle costs £6 per journey leg.""",
        [
            _mcq(
                "What is the average speed of the 07:35 ferry?",
                ["48 km/h", "50 km/h", "52 km/h", "54 km/h", "57.6 km/h"], "A",
                "A is correct: 72 km in 90 minutes = 72/1.5 = 48 km/h. B, C, and D use incorrect time conversions; E divides by 1.25 hours.", "Easy"),
            _mcq(
                "A passenger reaches Harbour at 08:55. What is the earliest ferry they can board, and when does it arrive?",
                ["09:20, arriving 10:42", "11:10, arriving 12:30", "09:20, arriving 10:35", "11:10, arriving 12:22", "They cannot travel that day"], "B",
                "B is correct: boarding for 09:20 closes at 09:05, so the 11:10 is first available and arrives 12:30. A ignores check-in; C and D invent arrival times; E ignores the later service.", "Medium"),
            _mcq(
                "What is the advance return cost for the 11:10 outward and 17:05 return ferries with a bicycle on both legs?",
                ["£51.04", "£58.00", "£63.04", "£65.04", "£70.00"], "C",
                "C is correct: fares (£31+£27)×0.88 = £51.04; bicycle charges add £12, total £63.04. A omits the bicycle; B ignores discount and bicycle; D discounts one leg only; E ignores the discount.", "Hard"),
            _mcq(
                "Which return ferry has the lowest listed fare per minute of travel, to the nearest penny?",
                ["15:15 at £0.35/min", "17:05 at £0.35/min", "17:05 at £0.33/min", "19:10 at £0.25/min", "19:10 at £0.32/min"], "D",
                "D is correct: £24/95 = about £0.25 per minute. The 15:15 is £30/85≈£0.35; the 17:05 is £27/82≈£0.33. A and C are real but higher rates; B rounds incorrectly; E divides by 75 minutes.", "Medium"),
        ]),
    (
        "QR", "Tables, Charts & Data", "Community Fundraising Events",
        """Net proceeds equal ticket income plus sponsorship, less variable costs, fixed costs and a card fee of 2.4% of ticket income. The walk and quiz each receive sponsorship equal to 10% of ticket income. The concert receives fixed sponsorship of £1,200.

| Event | Attendees | Ticket per person | Variable cost per person | Fixed cost |
|---|---:|---:|---:|---:|
| Walk | 320 | £12.00 | £3.20 | £650 |
| Quiz | 180 | £18.00 | £5.00 | £900 |
| Concert | 240 | £25.00 | £9.50 | £1,800 |""",
        [
            _mcq(
                "What are the concert's net proceeds?",
                ["£2,616", "£2,736", "£2,832", "£2,880", "£2,976"], "E",
                "E is correct: £6,000 + £1,200 − £2,280 − £1,800 − £144 = £2,976. A omits sponsorship; B miscalculates the card fee; C omits part of variable cost; D omits the card fee.", "Medium"),
            _mcq(
                "What are the quiz's net proceeds?",
                ["£1,686.24", "£1,608.48", "£1,764.00", "£2,586.24", "£3,240.00"], "A",
                "A is correct: £3,240 + £324 − £900 − £900 − £77.76 = £1,686.24. B applies the fee twice; C omits the fee; D omits one £900 cost; E is gross ticket income.", "Hard"),
            _mcq(
                "What are the combined net proceeds from all three events?",
                ["£6,736.08", "£7,120.08", "£7,264.08", "£7,444.24", "£9,024.00"], "B",
                "B is correct: walk £2,457.84 + quiz £1,686.24 + concert £2,976 = £7,120.08. A omits walk sponsorship; C omits one card fee; D applies 10% sponsorship to the concert; E uses gross rather than net amounts.", "Hard"),
            _mcq(
                "Assuming its fixed sponsorship remains £1,200, what is the minimum number of concert attendees needed to cover all concert costs?",
                ["39", "40", "41", "42", "45"], "C",
                "C is correct: each attendee contributes £25−£9.50−2.4%×£25 = £14.90 toward the £600 net fixed gap; £600/£14.90 = 40.27, so 41 are required. A and B are below break-even; D and E exceed the minimum.", "Hard"),
        ]),
    (
        "QR", "Percentages & Percentage Change", "Solar-Site Output",
        """Estimated monthly energy is: installed capacity × 24 hours × 30 days × capacity factor × (1 − system loss).

| Site | Installed capacity | Summer factor | Winter factor | System loss |
|---|---:|---:|---:|---:|
| A | 80 kW | 22% | 8% | 6% |
| B | 120 kW | 18% | 10% | 8% |
| C | 95 kW | 20% | 9% | 5% |""",
        [
            _mcq(
                "What is Site A's estimated summer output, to the nearest kWh?",
                ["10,138 kWh", "10,800 kWh", "11,520 kWh", "11,912 kWh", "12,672 kWh"], "D",
                "D is correct: 80×720×0.22×0.94 = 11,911.68 kWh. A applies loss twice; B uses a 20% factor; C omits the capacity factor adjustment; E omits system loss.", "Medium"),
            _mcq(
                "What is Site B's estimated winter output, to the nearest kWh?",
                ["7,200 kWh", "7,603 kWh", "7,776 kWh", "7,862 kWh", "7,949 kWh"], "E",
                "E is correct: 120×720×0.10×0.92 = 7,948.8 kWh. A uses 100 kW; B applies 12% loss; C uses 90% efficiency; D rounds before applying the loss.", "Medium"),
            _mcq(
                "How much greater is Site C's estimated summer output than its winter output?",
                ["7,148 kWh", "6,840 kWh", "6,498 kWh", "7,524 kWh", "8,208 kWh"], "A",
                "A is correct: 95×720×0.95×(0.20−0.09) = 7,147.8 kWh. B omits system efficiency; C applies loss twice; D uses a 12-point factor gap; E uses gross summer output minus net winter incorrectly.", "Hard"),
            _mcq(
                "Across all three sites, what is average estimated winter output per day, to the nearest kWh?",
                ["575 kWh", "604 kWh", "621 kWh", "649 kWh", "666 kWh"], "B",
                "B is correct: monthly winter outputs are 4,331.52, 7,948.8 and 5,848.2 kWh; total 18,128.52/30 = 604.28 kWh per day. A applies all losses as 10%; C omits Site A's loss; D divides by 28 days; E omits losses.", "Hard"),
        ]),
    (
        "QR", "Ratios & Proportion", "Food Cooperative Orders",
        """The cooperative pays a £45 delivery charge for each product order. Supplier discounts apply to the product cost before delivery. Apples lose 5% of ordered weight during sorting; cheese loses 2%. Orders are placed in whole kilograms.

| Product | Price per kg | Discount threshold | Discount |
|---|---:|---:|---:|
| Apples | £2.40 | 150 kg or more | 8% |
| Rice | £1.80 | 200 kg or more | 12% |
| Cheese | £7.50 | 80 kg or more | 5% |""",
        [
            _mcq(
                "What is the delivered cost of ordering 180 kg of apples?",
                ["£397.44", "£432.00", "£442.44", "£466.20", "£477.00"], "C",
                "C is correct: 180×£2.40×0.92 + £45 = £442.44. A omits delivery; B omits both discount and delivery; D applies discount only to delivery; E ignores discount.", "Medium"),
            _mcq(
                "What is the minimum delivered cost of obtaining at least 120 kg of usable apples?",
                ["£333.60", "£345.00", "£349.20", "£349.80", "£357.00"], "D",
                "D is correct: ceil(120/0.95)=127 kg; this is below the discount threshold, so 127×£2.40 + £45 = £349.80. A ignores waste; B rounds ordered weight down; C uses 126.75 kg despite whole-kg ordering; E orders 130 kg.", "Hard"),
            _mcq(
                "What is the delivered cost of 250 kg of rice?",
                ["£396.00", "£405.00", "£420.00", "£432.00", "£441.00"], "E",
                "E is correct: 250×£1.80×0.88 + £45 = £441. A omits delivery; B applies a 10% discount; C deducts £30 rather than 12%; D applies discount to delivery too.", "Medium"),
            _mcq(
                "What is the minimum delivered cost of obtaining at least 100 kg of usable cheese?",
                ["£778.88", "£757.50", "£772.50", "£785.63", "£817.50"], "A",
                "A is correct: ceil(100/0.98)=103 kg; 103×£7.50×0.95 + £45 = £778.875, or £778.88. B ignores waste and delivery; C ignores waste; D rounds the required weight before dividing; E ignores the discount.", "Hard"),
        ]),
]


def _sjt_app(stem, correct, explanation, difficulty="Medium"):
    return _mcq(stem, [
        "A very appropriate thing to do",
        "Appropriate, but not ideal",
        "Inappropriate, but not awful",
        "A very inappropriate thing to do",
    ], correct, explanation, difficulty)


def _sjt_imp(stem, correct, explanation, difficulty="Medium"):
    return _mcq(stem, [
        "Very important",
        "Important",
        "Of minor importance",
        "Not important at all",
    ], correct, explanation, difficulty)


def _sjt_rank(stem, actions, most, least, explanation, difficulty="Hard"):
    return _mcq(
        stem + " Select the most appropriate and least appropriate actions.",
        actions,
        f"{most},{least}",
        explanation,
        difficulty,
    )


SJT_PASSAGE_SETS = [
    (
        "SJT", "Appropriateness Ratings", "An Unfamiliar Dental Scanner",
        """Mina, a dental student, is asked to take a digital scan while her supervising dentist deals with an urgent call. Mina has used a different scanner at university but not this model. The patient has already waited a long time and says they need to leave soon. The dentist remains responsible for the patient's care and is available if interrupted.""",
        [
            _sjt_app(
                "Tell the dentist that she is unfamiliar with this scanner and ask for guidance before starting.", "A",
                "A is correct. This is honest about competence, protects the patient, and lets the responsible supervisor decide how to proceed. B would undervalue a timely, proportionate request; C or D would be wrong because the action directly addresses the safety concern without unnecessary escalation.", "Easy"),
            _sjt_app(
                "With the dentist's knowledge, ask a trained student nearby to demonstrate the controls before Mina continues under supervision.", "B",
                "B is correct. A demonstration with the supervisor aware may help, but it is not ideal because another student cannot replace the dentist's supervision or confirm competence. A is too strong for an incomplete solution; C and D are too negative because it is a transparent attempt to obtain support.", "Medium"),
            _sjt_app(
                "Begin the scan, stop if she becomes uncertain, and mention her unfamiliarity only if a problem occurs.", "C",
                "C is correct. She should disclose the limitation before acting; delaying disclosure creates avoidable risk. D would be too severe because she plans to stop rather than persist through danger, while B would be too favourable because the central competence issue is not addressed in advance; A is plainly excessive.", "Medium"),
            _sjt_app(
                "Tell the patient that the scanner is broken so the appointment can be ended without admitting she is unfamiliar with it.", "D",
                "D is correct. The lie undermines trust, hides a competence issue from both patient and supervisor, and obstructs appropriate care. C is too mild for deliberate dishonesty; B and A would wrongly treat deception as potentially acceptable.", "Hard"),
        ]),
    (
        "SJT", "Importance Ratings", "A Case in the Study Group",
        """A medical student posts a summary of an unusual patient encounter in a private course messaging group to ask for revision help. No name is used, but the message includes the patient's age, occupation, rare condition, hospital ward and date of admission. Only students on the course can join the group, although messages can be copied or forwarded.""",
        [
            _sjt_imp(
                "The possibility that the combined details could identify the patient.", "A",
                "A is correct. Identifiability creates a direct confidentiality risk to the patient even without a name. B would understate a central professional duty; C and D are indefensible because the risk is immediate and material.", "Easy"),
            _sjt_imp(
                "That the group is restricted to students on the course.", "B",
                "B is correct. Restricted access reduces exposure and is relevant, but it does not remove the need for consent, minimisation, or secure handling because messages can be forwarded. A overstates the protection; C and D dismiss a relevant contextual safeguard.", "Medium"),
            _sjt_imp(
                "That the student wanted a rapid answer before a revision session.", "C",
                "C is correct. Time pressure explains the student's choice but carries little weight against confidentiality and safer ways to seek help. D is too dismissive because context can inform a supportive response; B or A would give convenience undue moral weight.", "Medium"),
            _sjt_imp(
                "The colour of the phone case visible in a screenshot of the message.", "D",
                "D is correct. The phone-case colour has no bearing on patient confidentiality, harm, or the response required. C would still assign it some relevance; A and B would distort priorities by elevating an irrelevant detail.", "Easy"),
        ]),
    (
        "SJT", "Appropriateness Ratings", "A Marking Error in Her Favour",
        """Leah receives a practical-examination mark that is ten points higher than the score shown on her assessor's signed feedback sheet. The higher mark moves her above the pass threshold. Results become final in three days. Leah believes the discrepancy is probably a data-entry error, although it is possible that a later moderation changed the mark.""",
        [
            _sjt_app(
                "Contact the examinations office promptly, provide the feedback sheet, and ask them to verify the recorded mark.", "A",
                "A is correct. It is honest, timely, and allows the authorised team to determine whether moderation or error explains the difference. B would understate an ideal response; C and D would be inappropriate because delay risks an inaccurate result becoming final.", "Easy"),
            _sjt_app(
                "Raise the discrepancy with her personal tutor at their scheduled meeting tomorrow and ask the tutor to contact the examinations office.", "B",
                "B is correct. It is honest and likely timely, but not ideal because Leah can contact the responsible office directly and the deadline is close. A is too strong given the avoidable intermediary and delay; C and D are too negative because the concern will still be reported before finalisation.", "Medium"),
            _sjt_app(
                "Ask classmates whether similar discrepancies occurred before deciding whether to report hers.", "C",
                "C is correct. Peer information may provide context but unnecessarily delays reporting and does not resolve her own record. D is too severe because she has not decided to conceal it; B is too favourable because classmates are not the authorised decision-makers; A is clearly excessive.", "Medium"),
            _sjt_app(
                "Destroy the feedback sheet and keep the higher mark unless the university contacts her.", "D",
                "D is correct. Destroying evidence to benefit from a likely error is deliberate dishonesty and threatens assessment integrity. C is too mild for concealment plus evidence destruction; A and B are incompatible with the conduct.", "Hard"),
        ]),
    (
        "SJT", "Importance Ratings", "A Colleague Falling Behind",
        """During a clinical placement, Omar notices that another student, Priya, has become unusually withdrawn and has missed two teaching sessions. Priya says she is dealing with family problems and asks Omar not to tell anyone. She has not described any patient-care error, but Omar has seen her arrive late and struggle to concentrate during handover.""",
        [
            _sjt_imp(
                "Whether Priya's concentration could create an immediate risk to patients or to herself.", "A",
                "A is correct. Immediate safety determines how urgently and how far Omar may need to escalate despite the request for privacy. B would underweight the central risk; C and D would ignore affected patients and Priya.", "Easy"),
            _sjt_imp(
                "Priya's wish to retain control over who is told about her family circumstances.", "B",
                "B is correct. Respect, privacy, and involving Priya in seeking support matter, provided safety is not compromised. A would make her preference absolute despite possible risk; C or D would fail to respect a colleague experiencing difficulty.", "Medium"),
            _sjt_imp(
                "Whether Priya might miss a planned student social event this weekend.", "C",
                "C is correct. It may reflect her wellbeing but is peripheral compared with concentration, attendance, support, and safety. D is too dismissive because withdrawal can add context; A or B would give a social plan disproportionate weight.", "Medium"),
            _sjt_imp(
                "Whether offering help could make Omar look disloyal to Priya.", "D",
                "D is correct. Protecting Omar's image should not guide action when a colleague may need support and safety could be affected. C still gives self-presentation some weight; A and B would wrongly elevate it over professional responsibilities.", "Hard"),
        ]),
    (
        "SJT", "Appropriateness Ratings", "Pressure to Simplify the Data",
        """Nadia is helping analyse a student research project. The supervisor asks her to exclude several valid responses because the result then becomes statistically significant. No pre-agreed exclusion rule applies. When Nadia questions this, the supervisor says the project deadline matters more than methodological detail and that the raw file can be overwritten after the final graph is produced.""",
        [
            _sjt_app(
                "Decline to alter the dataset, preserve the original file, and explain that any exclusions need a defensible documented rule.", "A",
                "A is correct. It protects research integrity, keeps evidence reviewable, and addresses the supervisor directly and proportionately. B would understate a complete first response; C and D would be inappropriate because compliance or concealment corrupts the work.", "Hard"),
            _sjt_app(
                "Pause the analysis and ask the supervisor to confirm the proposed exclusions and rationale in writing before Nadia proceeds.", "B",
                "B is correct. It creates a record and avoids immediate misconduct, but it is not ideal because written confirmation alone cannot make an unjustified exclusion acceptable; Nadia should also state the integrity concern and seek appropriate advice. A is too favourable; C and D are too negative because the action is cautious and transparent.", "Hard"),
            _sjt_app(
                "Remove the responses for the draft graph but keep a private copy so they can be restored if somebody challenges the result.", "C",
                "C is correct. Keeping a copy limits irreversible harm, but knowingly producing a misleading graph remains wrong and may influence decisions. D is too severe because evidence is preserved and restoration intended; B or A would wrongly excuse deliberate misrepresentation.", "Hard"),
            _sjt_rank(
                "Nadia decides she needs advice before the deadline.",
                [
                    "Contact the project's designated research-integrity adviser confidentially, describe the facts, and retain the untouched data.",
                    "Change the graph as requested and mention the exclusions only if the project is accepted for publication.",
                    "Delete the raw responses so nobody can later accuse either Nadia or the supervisor of selective analysis.",
                ], "A", "C",
                "A is most appropriate because it combines confidential escalation, factual reporting, and preservation of evidence. B knowingly circulates a misleading result and delays disclosure. C is least appropriate because destroying raw data is active concealment and makes correction or fair review impossible.", "Hard"),
            _sjt_rank(
                "The supervisor later says Nadia is being disloyal to the team.",
                [
                    "Calmly restate the methodological concern and propose an independent statistical review.",
                    "Send the supervisor a personal insult and copy the entire department into the message.",
                    "Agree to remove the data in exchange for the supervisor promising a strong reference.",
                ], "A", "C",
                "A is most appropriate because it keeps the discussion evidence-based and offers a proportionate way to resolve disagreement. B is unprofessional and public but leaves the data intact. C is least appropriate because it combines research misconduct with a personal inducement and directly compromises integrity.", "Hard"),
        ]),
    (
        "SJT", "Appropriateness Ratings", "A Discriminatory Request",
        """A patient tells student Haris that they do not want to be seen by a clinician from a particular ethnic background. The patient is not in immediate danger and has not described any problem with the clinician's care. Haris is the first team member to hear the request and can contact his supervising doctor.""",
        [
            _sjt_app(
                "Promise that the clinician will be removed from the patient's care without asking what has prompted the request.", "D",
                "D is correct. It validates discrimination, makes an unauthorised promise, and fails to distinguish prejudice from a genuine communication or care concern. C would be too mild; A or B would wrongly treat the action as professionally acceptable.", "Hard"),
            _sjt_app(
                "Acknowledge the patient calmly, ask whether there is a specific care concern, and discuss the request promptly with the supervising doctor.", "A",
                "A is correct. It listens without endorsing prejudice, checks for legitimate concerns, and involves the responsible clinician. B would understate this balanced response; C and D would be wrong because the action protects both patient communication and staff dignity.", "Medium"),
            _sjt_app(
                "Tell the supervising doctor about the request and ask them to lead a private conversation with the patient.", "B",
                "B is correct. Escalating to the supervisor is appropriate, but not ideal because Haris can first acknowledge the patient and clarify whether a specific concern exists. A overstates an incomplete response; C and D are too negative because he does not endorse the discriminatory request.", "Medium"),
            _sjt_app(
                "Tell the patient that the request will be ignored, end the conversation, and give no explanation.", "C",
                "C is correct. The discriminatory demand should not be endorsed, but abruptly ending communication may miss a legitimate underlying concern and is unlikely to de-escalate. D is too strong because Haris does not act on the prejudice; B or A would be too favourable for failing to listen or seek senior support.", "Medium"),
        ]),
    (
        "SJT", "Importance Ratings", "A Photograph from Placement",
        """A student posts a photograph of a hospital corridor to a private social-media story after placement. No patient face is visible. In the background, a whiteboard shows a bed number and part of a surname, and a distinctive visitor can be seen beside the bed. The post has been viewed by several friends and will disappear automatically after 24 hours.""",
        [
            _sjt_imp(
                "How many positive reactions the photograph has received.", "D",
                "D is correct. Popularity does not reduce or increase the confidentiality duty or determine how quickly the post should be removed and reported. C gives an irrelevant social signal some weight; A and B would seriously distort the risk assessment.", "Easy"),
            _sjt_imp(
                "Whether the visible details could allow the patient to be identified when combined.", "A",
                "A is correct. Partial surname, bed information, and a distinctive visitor can create identification risk even without a face. B underweights the central harm; C and D ignore patient privacy.", "Easy"),
            _sjt_imp(
                "Whether the placement's reporting process can help contain the disclosure and notify affected people appropriately.", "B",
                "B is correct. A prompt approved response is materially relevant, though the existence of a process is secondary to recognising and stopping the breach itself. A overstates the process as the central ethical fact; C and D undervalue containment and accountability.", "Medium"),
            _sjt_imp(
                "That the student may feel embarrassed when asking friends to delete screenshots.", "C",
                "C is correct. Embarrassment is real and may affect how supportively the issue is handled, but it is minor beside confidentiality and containment. D is too dismissive of a human factor; A or B would give the student's discomfort disproportionate importance.", "Medium"),
        ]),
    (
        "SJT", "Appropriateness Ratings", "A Skill Beyond His Competence",
        """During a simulation day, Elliot practises a procedure on a model and struggles with several steps. Later on placement, a busy clinician asks him to perform the same procedure on a patient while the clinician completes paperwork nearby. Elliot has observed it in practice but has not yet been signed off as competent. The patient assumes Elliot is qualified to carry it out.""",
        [
            _sjt_app(
                "Start the procedure without mentioning his status because the clinician is in the same room.", "D",
                "D is correct. Proximity is not adequate supervision, the patient has a mistaken understanding, and Elliot knows he is not competent. C is too mild for knowingly exposing the patient to avoidable risk; A and B are incompatible with the lack of disclosure and supervision.", "Hard"),
            _sjt_app(
                "Tell the clinician that he is not signed off, clarify this with the patient, and request direct supervision or an alternative plan.", "A",
                "A is correct. It is honest, protects consent and safety, and seeks a proportionate way for care and learning to continue. B would understate a complete response; C and D would be wrong because the central risks are addressed before action.", "Easy"),
            _sjt_app(
                "Ask to observe the clinician perform it once more, but do not mention to the patient that he was initially asked to do it.", "B",
                "B is correct. Further observation is safer and educational, but not ideal because the patient's mistaken assumption and the original delegation should be clarified. A is too favourable; C and D are too negative because Elliot avoids practising beyond competence.", "Medium"),
            _sjt_app(
                "Pretend to feel suddenly unwell so somebody else performs the procedure, without explaining the competence concern.", "C",
                "C is correct. It avoids immediate patient risk but is dishonest and leaves the unsafe delegation unaddressed for the future. D is too severe because the patient is not exposed; B and A are too favourable because deception is unnecessary.", "Medium"),
        ]),
]


SJT_PASSAGE_SETS.extend([
    (
        "SJT", "Appropriateness Ratings", "An Expensive Thank-You Gift",
        """After a placement ends, the family of a patient gives student Mei a sealed envelope and says it contains a gift voucher to thank her for listening to them. They refuse to say its value and insist that declining it would be disrespectful. The placement has a gifts policy, but Mei cannot remember the value limit. Her supervisor is available later that day.""",
        [
            _sjt_app(
                "Open the envelope privately, keep the voucher if it is valuable, and tell nobody so the family is not embarrassed.", "D",
                "D is correct. Secretly accepting a potentially valuable gift creates probity and boundary concerns and deliberately avoids the policy. C is too mild for concealment motivated by personal benefit; A and B would wrongly normalise the conduct.", "Hard"),
            _sjt_app(
                "Thank the family, explain that she must check the gifts policy, and ask her supervisor how the gift should be handled before accepting it.", "A",
                "A is correct. It is respectful, transparent, and obtains authorised guidance before a boundary is crossed. B would understate this proportionate response; C and D are inappropriate because the action protects trust and both parties.", "Easy"),
            _sjt_app(
                "Ask her supervisor to hold the sealed envelope while Mei checks the policy with the placement office.", "B",
                "B is correct. It prevents personal acceptance and creates transparency, but is not ideal because Mei should also explain the position directly to the family rather than simply transfer the envelope. A is too strong for the incomplete communication; C and D are too negative because the risk is contained.", "Medium"),
            _sjt_app(
                "Hand the envelope back without explanation and leave immediately, even though the family appears upset and confused.", "C",
                "C is correct. Declining avoids a boundary problem, but the abrupt unexplained response is insensitive and may damage trust when a brief policy explanation was possible. D is too severe because Mei does not accept the gift; B and A are too favourable because communication is unnecessarily poor.", "Medium"),
        ]),
    (
        "SJT", "Appropriateness Ratings", "The Group Project Record",
        """Five students submit a joint project. After submission, Arjun discovers that one teammate copied several measurements from last year's project rather than collecting them. The copied values support the group's conclusion. The teammate says nobody was harmed, asks Arjun to stay quiet, and offers to replace the values only if the tutor asks questions.""",
        [
            _sjt_app(
                "Delete the messages showing what happened and agree on a shared explanation in case the tutor asks.", "D",
                "D is correct. Coordinated concealment and destruction of evidence deepen academic dishonesty and prevent fair correction. C is too mild for an active cover-up; A and B are incompatible with integrity and accountability.", "Hard"),
            _sjt_app(
                "Tell the group what he found, preserve the evidence, and contact the tutor promptly to ask how the submitted work should be corrected.", "A",
                "A is correct. It is transparent, protects the integrity of the assessment, and allows an authorised fair remedy for all group members. B would understate a complete response; C and D would be wrong because delay or concealment compounds the problem.", "Medium"),
            _sjt_app(
                "Speak to the teammate privately, ask them to tell the group and tutor themselves that day, and make clear that Arjun will report it if they do not.", "B",
                "B is correct. It gives the teammate a brief opportunity to take responsibility while setting a clear timely boundary, but it is not ideal because the submitted group work may require immediate action by the whole group. A is too strong; C and D are too negative because accountability remains likely and delay is limited.", "Medium"),
            _sjt_rank(
                "The teammate refuses to disclose the copied measurements.",
                [
                    "Report the facts and preserved evidence to the tutor, avoiding claims about motives that Arjun cannot prove.",
                    "Do nothing because the copied values happened to support the conclusion.",
                    "Alter the contribution log to show that a different student collected the measurements.",
                ], "A", "C",
                "A is most appropriate because it reports verifiable facts through the responsible channel and avoids speculation. B leaves known misconduct and an unreliable submission uncorrected. C is least appropriate because it creates a second false record and wrongfully implicates another student.", "Hard"),
            _sjt_rank(
                "The group wants to repair the project before meeting the tutor.",
                [
                    "Recollect what data can be collected, label every change, and give the tutor both versions with an explanation.",
                    "Invent replacement readings that preserve the same conclusion but look less similar to last year's values.",
                    "Remove the entire results section without telling the tutor that the submitted version contained copied data.",
                ], "A", "B",
                "A is most appropriate because it corrects transparently and preserves an audit trail for a fair academic decision. C removes information but still conceals what was submitted. B is least appropriate because fabricated readings repeat and extend the underlying dishonesty.", "Hard"),
        ]),
    (
        "SJT", "Importance Ratings", "A Senior Speaks Disrespectfully",
        """During a ward discussion, a senior doctor repeatedly interrupts a nurse and mocks the nurse's accent. The nurse becomes quiet and later makes a handover correction only after the doctor has left. Student Sofia is unsure whether the behaviour was an isolated lapse or part of a pattern. A patient heard part of the exchange.""",
        [
            _sjt_imp(
                "Whether raising the concern in front of everyone could embarrass the senior doctor.", "C",
                "C is correct. Avoiding unnecessary public confrontation may shape the route chosen, but it is minor compared with respectful teamwork, patient confidence, and safe communication. D is too dismissive because manner affects effectiveness; A or B would let the senior's embarrassment dominate the response.", "Medium"),
            _sjt_imp(
                "Whether Sofia hopes the senior doctor will write her a favourable reference.", "D",
                "D is correct. Personal career advantage should not determine whether disrespect and possible communication risk are addressed. C still gives self-interest some weight; A and B would seriously conflict with integrity.", "Hard"),
            _sjt_imp(
                "Whether the behaviour could discourage team members from speaking up about patient care.", "A",
                "A is correct. A silenced team can create direct patient-safety risk as well as harm the nurse, making this central. B would understate the consequence; C and D would ignore important stakeholders and immediate risk.", "Easy"),
            _sjt_imp(
                "The need to choose a timely, factual and proportionate route for raising the concern.", "B",
                "B is correct. The route matters for fairness and effectiveness, although it is secondary to recognising that the behaviour and safety implications require attention. A overstates process itself as the primary harm; C and D undervalue responsible escalation.", "Medium"),
        ]),
    (
        "SJT", "Appropriateness Ratings", "A Patient Sends a Personal Message",
        """After meeting student Daniel at an outpatient clinic, a patient finds his public social-media profile and sends him a private message. The message asks when the next appointment is and adds a question about new symptoms. The clinic has a secure patient portal and a telephone advice route. Daniel has no clinical responsibility outside the supervised placement.""",
        [
            _sjt_app(
                "Reply only with the appointment time from memory, then ask the patient to use the portal for the symptom question.", "C",
                "C is correct. Redirecting symptoms is sensible, but using a personal account and relying on memory still crosses boundaries and risks inaccurate information. D is too severe because Daniel limits the content and redirects risk; B or A would be too favourable given the avoidable channel breach.", "Medium"),
            _sjt_app(
                "Discuss the symptoms in detail by private message and advise the patient what treatment to start.", "D",
                "D is correct. Daniel uses an insecure personal channel, acts beyond his supervised role, and creates immediate risk through unsupervised advice. C is too mild; A and B are incompatible with the boundary and safety failures.", "Hard"),
            _sjt_app(
                "Do not discuss any patient information on social media; direct the patient to the portal or advice line and inform the supervisor through the approved route.", "A",
                "A is correct. It preserves boundaries and confidentiality, gives the patient a safe route, and keeps the responsible team informed. B would understate a complete response; C and D would be wrong because the action addresses rather than ignores the message.", "Easy"),
            _sjt_app(
                "Send a brief message asking the patient to telephone the clinic, but do not tell the supervisor that contact occurred.", "B",
                "B is correct. It redirects the patient without clinical advice, but is not ideal because a personal reply still confirms contact and the supervised team should know about the boundary issue. A is too strong; C and D are too negative because risk is limited and no confidential detail is discussed.", "Medium"),
        ]),
    (
        "SJT", "Importance Ratings", "A Patient Who Needs an Interpreter",
        """A patient with limited English attends a consultation about whether to proceed with a non-urgent investigation. The booked interpreter is delayed. The patient's adult neighbour offers to interpret and says the patient wants to finish quickly. The clinician's next appointments are already running late, and the patient nods when shown the consent form.""",
        [
            _sjt_imp(
                "That waiting for the interpreter may delay later appointments.", "C",
                "C is correct. Delay affects service flow and deserves practical consideration, but it is minor beside valid understanding, voluntariness, and confidentiality. D is too dismissive of operational impact; A or B would allow convenience to outweigh informed decision-making.", "Medium"),
            _sjt_imp(
                "Whether the clinician would appear more skilled by managing without language support.", "D",
                "D is correct. The clinician's image is irrelevant; appearing capable must not displace the patient's understanding and safety. C would still give vanity some weight; A and B would invert professional priorities.", "Hard"),
            _sjt_imp(
                "Whether the patient can understand the purpose, material choices and consequences before deciding.", "A",
                "A is correct. Genuine understanding is central to an informed, voluntary decision and directly protects the patient. B would understate this requirement; C and D would ignore the core ethical issue.", "Easy"),
            _sjt_imp(
                "Whether using the neighbour could affect accuracy, privacy or the patient's freedom to speak.", "B",
                "B is correct. These are important reasons to prefer qualified language support, though context such as urgency and the patient's wishes also matters. A can be too absolute because the consideration informs rather than alone determines every response; C and D undervalue real communication risks.", "Medium"),
        ]),
    (
        "SJT", "Appropriateness Ratings", "Too Tired to Work Safely",
        """After caring for a relative overnight, student Grace begins a morning placement having slept for two hours. She feels light-headed and misreads a room number, although no patient is affected. Her supervisor asks her to help with a task requiring sustained concentration. Grace worries that leaving will burden the team and count against her attendance.""",
        [
            _sjt_app(
                "Complete only the task's first few steps and decide later whether her concentration is adequate.", "C",
                "C is correct. Testing herself during a concentration-dependent task exposes others to avoidable risk after clear warning signs. D is too severe because she intends to reassess rather than conceal harm; B or A would be too favourable because safety should be addressed before starting.", "Medium"),
            _sjt_app(
                "Hide the room-number error, drink several energy drinks, and tell the supervisor she is fully fit.", "D",
                "D is correct. It combines dishonesty with failure to address impairment and may expose patients or colleagues to risk. C is too mild for concealment and false reassurance; A and B are plainly inconsistent with the conduct.", "Hard"),
            _sjt_app(
                "Tell the supervisor immediately about the sleep loss and symptoms, stop the concentration-dependent task, and agree a safe plan for the day.", "A",
                "A is correct. It is honest, prioritises safety, and lets the supervisor consider rest, alternative duties, or leaving. B would understate a complete proportionate response; C and D would be wrong because the risk is addressed before harm.", "Easy"),
            _sjt_rank(
                "The supervisor offers three immediate plans.",
                [
                    "Move Grace to non-clinical observation while arrangements are made for her to rest or go home safely.",
                    "Keep Grace on the same task but ask a patient to alert staff if she seems confused.",
                    "Record her as present and send her to sleep alone in an unlocked patient room without telling the team.",
                ], "A", "B",
                "A is most appropriate because it removes the safety-critical duty, keeps supervision, and addresses Grace's welfare. C also uses an unsuitable space and hides her location, but at least removes her from the task. B is least appropriate because it retains the known risk and transfers monitoring responsibility to a patient.", "Hard"),
            _sjt_rank(
                "Grace sees another student in the same condition later that week.",
                [
                    "Check on the student privately and encourage them to tell the supervisor before undertaking safety-critical work.",
                    "Offer to sign the student's attendance sheet if they leave without telling anyone.",
                    "Tell the entire student group that the student is unsafe before asking them what is wrong.",
                ], "A", "B",
                "A is most appropriate because it is supportive, private, and directs the safety concern to the responsible person. C is disproportionate and publicly humiliating but could still prompt attention. B is least appropriate because falsifying attendance actively enables concealment of a safety issue.", "Hard"),
        ]),
    (
        "SJT", "Appropriateness Ratings", "A Relative Calls for Information",
        """While helping at a reception desk, student Imani receives a call from someone who says they are a patient's brother. The caller knows the patient's full name and date of birth and asks whether the patient attended today and what the clinician found. The record contains no permission to share information with this person. Staff can use an approved verification and message process.""",
        [
            _sjt_app(
                "Take the caller's contact details without confirming attendance, explain that staff must verify permission, and pass a message through the approved process.", "B",
                "B is correct. It protects confidentiality and offers a legitimate route, but it is not ideal for Imani to handle more than necessary if trained reception staff are immediately available. A would overstate an incomplete but safe response; C and D are too negative because no patient information is disclosed.", "Medium"),
            _sjt_app(
                "Confirm only that the patient attended, but refuse to discuss what the clinician found.", "C",
                "C is correct. Limiting detail reduces harm, but attendance itself is confidential and the caller's knowledge does not prove authority. D is too severe because no findings are shared; B or A would be too favourable because a disclosure still occurs.", "Medium"),
            _sjt_app(
                "Read the clinician's findings to the caller because he supplied two correct identifiers.", "D",
                "D is correct. Identifiers help locate a record but do not establish consent or entitlement, and sharing findings is a serious breach. C is too mild for extensive disclosure; A and B are incompatible with confidentiality.", "Hard"),
            _sjt_app(
                "State that she cannot confirm any information, refer the call to trained staff using the approved process, and document the request as required.", "A",
                "A is correct. It preserves confidentiality, uses the proper route, and creates accountability without abandoning the caller. B would understate an ideal response; C and D would be wrong because the action is proportionate and helpful.", "Easy"),
            _sjt_rank(
                "The caller becomes angry and says the patient is at risk.",
                [
                    "Alert a qualified team member immediately to assess the claimed risk without confirming patient information to the caller.",
                    "End the call and delete the number so no further contact is possible.",
                    "Share the record to calm the caller, then ask the patient for permission later.",
                ], "A", "C",
                "A is most appropriate because it takes the safety claim seriously while preserving confidentiality and involving someone qualified. B may miss a genuine concern and removes an audit trail. C is least appropriate because it makes an unauthorised disclosure first and treats consent as retrospective.", "Hard"),
        ]),
    (
        "SJT", "Appropriateness Ratings", "A Patient Appears Unsure",
        """Dental student Rowan observes a clinician explaining a non-urgent procedure. The explanation is rapid because the clinic is late. The patient repeatedly looks at a companion before answering and signs the form after the clinician says, “We need to get on.” Earlier, the patient had asked for more time to think. Rowan can speak to the clinician during the consultation.""",
        [
            _sjt_app(
                "Wait until the end of the session and privately ask the clinician whether the patient really understood.", "B",
                "B is correct. A private question is respectful and may improve future practice, but it is not ideal because the patient's present decision may already be proceeding without adequate understanding. A overstates a delayed response; C and D are too negative because the concern is still raised.", "Medium"),
            _sjt_app(
                "Remain silent during the consultation, then mention the incident in a student reflective diary without telling anyone responsible for the patient's care.", "C",
                "C is correct. Reflection has educational value but does not address the current patient's possible lack of understanding or allow correction. D is too severe because Rowan does not cause further harm; B or A would be too favourable for a response confined to private learning.", "Medium"),
            _sjt_app(
                "Add Rowan's own signature beside the patient's to show that two people agree the procedure should happen.", "D",
                "D is correct. Rowan cannot substitute personal agreement for the patient's informed voluntary decision, and the extra signature could falsely legitimise pressure. C is too mild for creating a misleading record; A and B are incompatible with the action.", "Hard"),
            _sjt_app(
                "Respectfully pause and say that the patient appears uncertain, asking whether the explanation and decision need more time before proceeding.", "A",
                "A is correct. It raises an observable concern promptly, supports the patient's autonomy, and allows the responsible clinician to reassess without accusation. B would understate this proportionate intervention; C and D would be wrong because it directly protects the patient.", "Hard"),
            _sjt_rank(
                "The clinician agrees to pause and offers three next steps.",
                [
                    "Check the patient's understanding in their own words and offer time or a later appointment without pressure.",
                    "Ask the companion to decide because the patient looked at them for reassurance.",
                    "Proceed immediately because a signed form proves the decision was informed and voluntary.",
                ], "A", "C",
                "A is most appropriate because it tests understanding and restores a voluntary choice. B wrongly transfers the decision to the companion without evidence of authority. C is least appropriate because it ignores the observed uncertainty and treats a pressured signature as conclusive.", "Hard"),
        ]),
])


PASSAGE_SETS = list(VR_PASSAGE_SETS) + list(QR_PASSAGE_SETS) + list(SJT_PASSAGE_SETS)
STANDALONE_QUESTIONS = list(DM_STANDALONE_QUESTIONS)
