# -*- coding: utf-8 -*-
"""
Seed demo data for the company side of the prototype.

Writes realistic quote requests into server/data/company_signups.json so the
internal pipeline view has something to show.

Company names are FICTIONAL on purpose: stating that a real business requested a
quote would be a false claim about that business. Email domains use example.com
so nothing can be sent to a real address by accident.

    .venv/bin/python tools/seed_demo.py          # replace with the demo set
    .venv/bin/python tools/seed_demo.py --clear  # empty it
"""
import datetime
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(os.path.dirname(HERE), "server", "data", "company_signups.json")

NOW = datetime.datetime.now(datetime.timezone.utc)


def days_ago(n, hour=10, minute=0):
    stamp = (NOW - datetime.timedelta(days=n)).replace(
        hour=hour, minute=minute, second=0, microsecond=0)
    return stamp.isoformat(timespec="seconds")


ROWS = [
    {
        "company": "Groupe Solveny", "contact_name": "Camille Fournier",
        "email": "c.fournier@example.com", "phone": "+33 1 44 21 09 55",
        "org_size": "s3", "programme": "Fonds Solidarité Alimentaire",
        "message": "Nous finançons depuis quatre ans des projets de lutte contre la précarité "
                   "alimentaire près de nos entrepôts. Nous recevons environ 200 dossiers par an "
                   "et n'avons pas les moyens de tous les instruire.",
        "status": "new", "received_at": days_ago(1, 9, 12),
    },
    {
        "company": "Fondation Maribel", "contact_name": "Théo Nguyen",
        "email": "contact@example.com", "phone": "",
        "org_size": "s6", "programme": "Appel à projets Jeunesse et Insertion",
        "message": "Fondation abritée, deux sessions par an. Notre difficulté principale est la "
                   "qualité des pièces justificatives transmises.",
        "status": "contacted", "received_at": days_ago(3, 14, 40),
    },
    {
        "company": "Verdoyer & Cie", "contact_name": "Anne-Laure Petit",
        "email": "al.petit@example.com", "phone": "+33 4 78 33 12 00",
        "org_size": "s2", "programme": "Mécénat de proximité",
        "message": "Petite entreprise familiale, budget de mécénat de 40 000 € par an. "
                   "Nous cherchons des associations dans un rayon de 50 km.",
        "status": "quoted", "received_at": days_ago(6, 11, 5),
    },
    {
        "company": "Banque Tramontane", "contact_name": "Julien Mercier",
        "email": "j.mercier@example.com", "phone": "+33 5 61 22 88 41",
        "org_size": "s4", "programme": "Programme Territoires Solidaires",
        "message": "39 caisses régionales, chacune avec son propre comité. Nous voulons "
                   "harmoniser le sourcing des associations.",
        "status": "new", "received_at": days_ago(2, 16, 20),
    },
    {
        "company": "Delcourt Distribution", "contact_name": "Sophie Arnaud",
        "email": "s.arnaud@example.com", "phone": "+33 3 20 45 77 10",
        "org_size": "s5", "programme": "Anti-gaspi & Solidarité",
        "message": "Dons en nature sur 180 magasins plus une enveloppe de mécénat. "
                   "Nous avons besoin de vérifier l'habilitation aide alimentaire des "
                   "associations avant de conventionner.",
        "status": "won", "received_at": days_ago(14, 10, 0),
    },
    {
        "company": "Atelier Novem", "contact_name": "Marc Ellouze",
        "email": "marc@example.com", "phone": "",
        "org_size": "s1", "programme": "Arrondi solidaire en caisse",
        "message": "32 salariés. Nous lançons un arrondi en caisse et cherchons une "
                   "association bénéficiaire crédible.",
        "status": "new", "received_at": days_ago(0, 8, 45),
    },
    {
        "company": "Fondation Pierrelune", "contact_name": "Inès Bouchard",
        "email": "i.bouchard@example.com", "phone": "+33 1 53 90 14 22",
        "org_size": "s6", "programme": "Fonds Alimentation Durable",
        "message": "Nous finançons 25 projets par an à hauteur de 15 000 à 60 000 €. "
                   "Le reporting d'impact des bénéficiaires est notre point faible.",
        "status": "contacted", "received_at": days_ago(8, 15, 30),
    },
    {
        "company": "Transport Aurelis", "contact_name": "Karim Benali",
        "email": "k.benali@example.com", "phone": "+33 2 40 19 63 07",
        "org_size": "s3", "programme": "Logistique Solidaire",
        "message": "Nous mettons à disposition des véhicules réfrigérés. Nous voulons "
                   "identifier les associations capables d'assurer la chaîne du froid.",
        "status": "quoted", "received_at": days_ago(10, 13, 15),
    },
]


def main():
    if "--clear" in sys.argv[1:]:
        io.open(TARGET, "w", encoding="utf-8").write("[]")
        print("cleared %s" % TARGET)
        return 0

    directory = os.path.dirname(TARGET)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with io.open(TARGET, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(ROWS, ensure_ascii=False, indent=1))

    counts = {}
    for row in ROWS:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print("seeded %d demo quote requests -> %s" % (len(ROWS), TARGET))
    for status in ("new", "contacted", "quoted", "won"):
        print("   %-10s %d" % (status, counts.get(status, 0)))
    print("\n   All company names are fictional; emails use example.com.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
