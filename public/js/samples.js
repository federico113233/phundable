// Demo charity profiles for the onboarding form.
//
// Three deliberately different organisations, so the scoring can be seen to
// discriminate rather than just produce a number: a small local food-aid
// association, a mid-size urban youth charity, and a large environmental one
// that is genuinely EU-grant ready. Every value matches an option declared in
// server/config/onboarding_fields.json.

export const SAMPLES = [
  {
    id: "food",
    label: { fr: "Aide alimentaire", en: "Food aid" },
    hint: { fr: "Petite association locale", en: "Small local charity" },
    profile: {
      org_name: "Les Paniers Solidaires",
      legal_status: "association_1901",
      accreditations: ["interet_general", "esus", "aide_alimentaire"],
      siret_rna: "W313004521",
      year_founded: 2019,
      website: "https://paniers-solidaires.example.org",
      cause_areas: ["food_waste", "food_security", "poverty", "circular_economy"],
      mission_statement:
        "Nous récupérons les invendus alimentaires de la grande distribution en Occitanie " +
        "et les redistribuons à des familles en situation de précarité, via un réseau de " +
        "12 points de distribution animé par 140 bénévoles.",
      target_groups: ["families", "students", "homeless"],
      beneficiaries_per_year: 4200,
      annual_budget_eur: 380000,
      employees_count: 6,
      volunteers_count: 140,
      country: "FR",
      regions: ["occitanie"],
      has_audited_accounts: true,
      cofinancing_capacity_pct: 15,
      can_report_in_english: false,
      grant_experience: "local",
      has_grant_writer: false,
      project_title: "Chaîne du froid solidaire",
      project_description:
        "Acquisition de deux véhicules réfrigérés et d'une chambre froide pour doubler " +
        "notre capacité de collecte d'invendus frais sur l'agglomération toulousaine, " +
        "et réduire les pertes lors du transport.",
      amount_sought_eur: 45000,
      project_duration_months: 18,
    },
  },
  {
    id: "youth",
    label: { fr: "Jeunesse & insertion", en: "Youth & inclusion" },
    hint: { fr: "Structure urbaine moyenne", en: "Mid-size urban charity" },
    profile: {
      org_name: "Horizon Jeunes",
      legal_status: "association_1901",
      accreditations: ["interet_general", "jeunesse_education"],
      siret_rna: "W751208834",
      year_founded: 2012,
      website: "https://horizon-jeunes.example.org",
      cause_areas: ["youth", "education", "social_inclusion", "employment"],
      mission_statement:
        "Nous accompagnons des jeunes de 16 à 25 ans issus des quartiers prioritaires " +
        "d'Île-de-France vers la formation et l'emploi, par du mentorat individuel et " +
        "des ateliers collectifs animés par des professionnels bénévoles.",
      target_groups: ["youth", "students", "unemployed"],
      beneficiaries_per_year: 1350,
      annual_budget_eur: 850000,
      employees_count: 14,
      volunteers_count: 60,
      country: "FR",
      regions: ["ile_de_france"],
      has_audited_accounts: true,
      cofinancing_capacity_pct: 30,
      can_report_in_english: true,
      grant_experience: "national",
      has_grant_writer: true,
      project_title: "Mentorat vers l'emploi",
      project_description:
        "Déploiement d'un programme de mentorat sur quatre nouveaux quartiers " +
        "prioritaires, avec le recrutement de deux coordinateurs et la formation de " +
        "80 mentors bénévoles issus du monde de l'entreprise.",
      amount_sought_eur: 120000,
      project_duration_months: 24,
    },
  },
  {
    id: "env",
    label: { fr: "Environnement", en: "Environment" },
    hint: { fr: "Grande structure, prête pour l'UE", en: "Large, EU-ready" },
    profile: {
      org_name: "Terre Vivante",
      legal_status: "association_1901",
      accreditations: ["interet_general", "rup"],
      siret_rna: "W691003277",
      year_founded: 2008,
      website: "https://terre-vivante.example.org",
      cause_areas: ["environment", "climate", "circular_economy", "food_waste"],
      mission_statement:
        "Nous concevons et déployons des filières de réemploi et de valorisation des " +
        "biodéchets avec les collectivités et les industriels, et formons les acteurs " +
        "locaux à la mesure de leur impact environnemental.",
      target_groups: ["general_public"],
      beneficiaries_per_year: 26000,
      annual_budget_eur: 2100000,
      employees_count: 28,
      volunteers_count: 95,
      country: "FR",
      regions: ["auvergne_rhone_alpes", "national", "europe"],
      has_audited_accounts: true,
      cofinancing_capacity_pct: 45,
      can_report_in_english: true,
      grant_experience: "eu",
      has_grant_writer: true,
      project_title: "Démonstrateur biodéchets circulaires",
      project_description:
        "Mise en place d'un démonstrateur de valorisation des biodéchets sur trois " +
        "territoires européens, avec quantification des tonnages évités et des " +
        "émissions de CO2e, en consortium avec deux partenaires espagnols et belges.",
      amount_sought_eur: 400000,
      project_duration_months: 36,
    },
  },
];
